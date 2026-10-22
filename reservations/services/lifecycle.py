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
    # Expiry is bookkeeping, not part of this attempt: it is committed on its
    # own, so a refused reservation does not roll it back (same as approvals).
    expire_stale_approvals()
    with transaction.atomic():
        reservation = create_draft(user=user, resource=resource, reservation_date=reservation_date)
        return confirm_reservation(reservation)


def lock_for_allocation(reservation: Reservation) -> Reservation:
    """Reload the reservation and lock its row and its resource's row (C04, Q-1).

    Locking the resource row is the authoritative point for BR-02 under
    concurrency: two allocations of the same resource wait for each other, so
    the second one sees the first one's CONFIRMED in ``ensure_can_allocate``.
    The partial unique index stays as the last guard. Call inside a transaction.
    """
    return (
        Reservation.objects.select_for_update(of=("self", "resource"))
        .select_related("resource", "user")
        .get(pk=reservation.pk)
    )


def confirm_reservation(reservation: Reservation) -> Reservation:
    # Expiry runs outside the transaction below, so a refused confirmation
    # does not roll it back (C02 evidence, finding 2).
    expire_stale_approvals()
    return _confirm(reservation)


@transaction.atomic
def _confirm(reservation: Reservation) -> Reservation:
    reservation = lock_for_allocation(reservation)

    if reservation.status != Reservation.Status.DRAFT:
        raise ReservationError("Only draft reservations can be confirmed.")

    ensure_can_allocate(reservation)

    # A resource that needs approval does not get allocated here: confirming it
    # creates a request instead (BR-05). Everything else is unchanged.
    if reservation.resource.requires_approval:
        reservation.status = Reservation.Status.PENDING_APPROVAL
        reservation.save(update_fields=["status", "updated_at"])
        notify_after_commit("requested approval", reservation)
        return reservation

    allocate(reservation)
    notify_after_commit("confirmed", reservation)
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


def notify_after_commit(action: str, reservation: Reservation) -> None:
    """Announce a state change once it is stored (H1: commit, then notify).

    Inside a transaction the event waits for the commit and is dropped on
    rollback, so nobody hears about a change that never happened. Outside a
    transaction Django runs it immediately.
    """
    transaction.on_commit(lambda: notify_reservation_event(action, reservation))


def cancel_reservation(reservation: Reservation, *, actor) -> Reservation:
    # Expiry runs outside the transaction below, like in confirm and approve.
    expire_stale_approvals()
    return _cancel(reservation, actor=actor)


@transaction.atomic
def _cancel(reservation: Reservation, *, actor) -> Reservation:
    reservation = Reservation.objects.select_for_update().select_related("user").get(pk=reservation.pk)

    if reservation.user_id != actor.id:
        raise ReservationError("You can only cancel your own reservation.")

    if reservation.status not in CANCELLABLE_STATUSES:
        raise ReservationError("Only a draft, pending or confirmed reservation can be cancelled.")

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    notify_after_commit("cancelled", reservation)
    return reservation
