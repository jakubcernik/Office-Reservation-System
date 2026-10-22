from django.db import IntegrityError, transaction

from ..integrations.notifications import notify_reservation_event
from ..models import Reservation, Resource
from .errors import ReservationError
from .expiry import expire_stale_approvals
from .rules import ensure_can_allocate

#: States the owner may still withdraw (BR-03 in the C02 specification).
CANCELLABLE_STATUSES = (
    Reservation.Status.DRAFT,
    Reservation.Status.PENDING_APPROVAL,
    Reservation.Status.CONFIRMED,
)


def create_draft(*, user, resource: Resource, reservation_date) -> Reservation:
    if not resource.is_active:
        raise ReservationError("Selected resource is not active.")

    return Reservation.objects.create(
        user=user,
        resource=resource,
        reservation_date=reservation_date,
        status=Reservation.Status.DRAFT,
    )


def create_reservation(*, user, resource: Resource, reservation_date) -> Reservation:
    """Create a reservation and settle its state in one step (v0.3 flow).

    The user asks for the resource once. Creating and confirming happen in the
    same transaction, so the result is `CONFIRMED`, or `PENDING_APPROVAL` when
    the resource requires an approval decision (BR-05). Nothing is left in
    `DRAFT`, and a failed check leaves no reservation behind at all.
    """
    with transaction.atomic():
        reservation = create_draft(user=user, resource=resource, reservation_date=reservation_date)
        return confirm_reservation(reservation)


@transaction.atomic
def confirm_reservation(reservation: Reservation) -> Reservation:
    expire_stale_approvals()
    reservation = Reservation.objects.select_for_update().select_related("resource", "user").get(pk=reservation.pk)

    if reservation.status != Reservation.Status.DRAFT:
        raise ReservationError("Only draft reservations can be confirmed.")

    ensure_can_allocate(reservation)

    # A resource that needs approval does not get allocated here: confirming it
    # creates a request instead (BR-05). Everything else is unchanged.
    if reservation.resource.requires_approval:
        reservation.status = Reservation.Status.PENDING_APPROVAL
        reservation.save(update_fields=["status", "updated_at"])
        notify_reservation_event("requested approval", reservation)
        return reservation

    allocate(reservation)
    notify_reservation_event("confirmed", reservation)
    return reservation


def allocate(reservation: Reservation) -> None:
    """Store the reservation as CONFIRMED; the DB index is the last guard of BR-02.

    Call inside a transaction, after ``ensure_can_allocate`` passed.
    """
    reservation.status = Reservation.Status.CONFIRMED
    try:
        reservation.save(update_fields=["status", "updated_at"])
    except IntegrityError as exc:
        raise ReservationError("The selected resource is already confirmed for that date.") from exc


@transaction.atomic
def cancel_reservation(reservation: Reservation, *, actor) -> Reservation:
    expire_stale_approvals()
    reservation = Reservation.objects.select_for_update().select_related("user").get(pk=reservation.pk)

    if reservation.user_id != actor.id:
        raise ReservationError("You can only cancel your own reservation.")

    if reservation.status not in CANCELLABLE_STATUSES:
        raise ReservationError("Only a draft, pending or confirmed reservation can be cancelled.")

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    notify_reservation_event("cancelled", reservation)
    return reservation
