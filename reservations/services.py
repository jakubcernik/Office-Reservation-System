import logging

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone

from .models import Reservation, Resource

logger = logging.getLogger(__name__)

#: Users in this group may decide about reservations that need approval.
MANAGER_GROUP_NAME = "Office Manager"

#: States the owner may still withdraw (BR-03 in the C02 specification).
CANCELLABLE_STATUSES = (
    Reservation.Status.DRAFT,
    Reservation.Status.PENDING_APPROVAL,
    Reservation.Status.CONFIRMED,
)


class ReservationError(Exception):
    """Raised when a reservation state change cannot be completed."""


def notify_reservation_event(action: str, reservation: Reservation) -> None:
    logger.info(
        "%s reservation id=%s user=%s resource=%s date=%s status=%s",
        action,
        reservation.pk,
        reservation.user_id,
        reservation.resource_id,
        reservation.reservation_date,
        reservation.status,
    )


def available_resources_for_date(reservation_date) -> QuerySet[Resource]:
    occupied_resource_ids = Reservation.objects.filter(
        reservation_date=reservation_date,
        status=Reservation.Status.CONFIRMED,
    ).values_list("resource_id", flat=True)
    return Resource.objects.filter(is_active=True).exclude(pk__in=occupied_resource_ids)


def user_can_approve(user) -> bool:
    """Office managers are staff accounts or members of the Office Manager group."""
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or user.is_superuser or user.groups.filter(name=MANAGER_GROUP_NAME).exists())


def expire_stale_approvals() -> int:
    """Move requests nobody decided in time to EXPIRED (BR-06).

    A request expires once the day it was made for is over, so the check is a
    plain comparison with today. It runs whenever reservations are read or
    changed, which is why the system needs no background job.
    """
    expired_count = Reservation.objects.filter(
        status=Reservation.Status.PENDING_APPROVAL,
        reservation_date__lt=timezone.localdate(),
    ).update(status=Reservation.Status.EXPIRED, updated_at=timezone.now())
    if expired_count:
        logger.info("Expired %s pending approval request(s).", expired_count)
    return expired_count


def pending_approval_requests() -> QuerySet[Reservation]:
    """Requests waiting for a decision, oldest reservation day first."""
    expire_stale_approvals()
    return (
        Reservation.objects.select_related("resource", "user")
        .filter(status=Reservation.Status.PENDING_APPROVAL)
        .order_by("reservation_date", "resource__name")
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


def user_has_confirmed_desk(user, reservation_date) -> bool:
    return Reservation.objects.filter(
        user=user,
        reservation_date=reservation_date,
        resource__resource_type=Resource.ResourceType.DESK,
        status=Reservation.Status.CONFIRMED,
    ).exists()


@transaction.atomic
def confirm_reservation(reservation: Reservation) -> Reservation:
    expire_stale_approvals()
    reservation = Reservation.objects.select_for_update().select_related("resource", "user").get(pk=reservation.pk)

    if reservation.status != Reservation.Status.DRAFT:
        raise ReservationError("Only draft reservations can be confirmed.")

    if not reservation.resource.is_active:
        raise ReservationError("The selected resource is no longer active.")

    if reservation.resource.resource_type == Resource.ResourceType.PARKING_SPOT:
        if not user_has_confirmed_desk(reservation.user, reservation.reservation_date):
            raise ReservationError("Parking requires a confirmed desk reservation for the same date.")

    if Reservation.objects.filter(
        resource=reservation.resource,
        reservation_date=reservation.reservation_date,
        status=Reservation.Status.CONFIRMED,
    ).exclude(pk=reservation.pk).exists():
        raise ReservationError("The selected resource is already confirmed for that date.")

    # A resource that needs approval does not get allocated here: confirming it
    # creates a request instead (BR-05). Everything else is unchanged.
    if reservation.resource.requires_approval:
        reservation.status = Reservation.Status.PENDING_APPROVAL
        reservation.save(update_fields=["status", "updated_at"])
        notify_reservation_event("requested approval", reservation)
        return reservation

    reservation.status = Reservation.Status.CONFIRMED
    try:
        reservation.save(update_fields=["status", "updated_at"])
    except IntegrityError as exc:
        raise ReservationError("The selected resource is already confirmed for that date.") from exc

    notify_reservation_event("confirmed", reservation)
    return reservation


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


def decide_approval(reservation: Reservation, *, actor, approve: bool) -> Reservation:
    """Office manager decides about a request waiting for approval (OP-05).

    Approving allocates the resource, so the rules are checked again: the world
    may have changed since the request was created (BR-07).
    """
    if not user_can_approve(actor):
        raise ReservationError("Only an office manager can decide about approval requests.")

    # Expiry is bookkeeping, not part of the decision, so it runs outside the
    # transaction below: a request that ran out of time has to stay expired even
    # when the decision itself is refused.
    expire_stale_approvals()
    return _apply_approval_decision(reservation, approve=approve)


@transaction.atomic
def _apply_approval_decision(reservation: Reservation, *, approve: bool) -> Reservation:
    reservation = Reservation.objects.select_for_update().select_related("resource", "user").get(pk=reservation.pk)

    if reservation.status != Reservation.Status.PENDING_APPROVAL:
        raise ReservationError("Only a reservation waiting for approval can be decided.")

    if not approve:
        reservation.status = Reservation.Status.REJECTED
        reservation.save(update_fields=["status", "updated_at"])
        notify_reservation_event("rejected", reservation)
        return reservation

    if not reservation.resource.is_active:
        raise ReservationError("The selected resource is no longer active.")

    if reservation.resource.resource_type == Resource.ResourceType.PARKING_SPOT:
        if not user_has_confirmed_desk(reservation.user, reservation.reservation_date):
            raise ReservationError("Parking requires a confirmed desk reservation for the same date.")

    if Reservation.objects.filter(
        resource=reservation.resource,
        reservation_date=reservation.reservation_date,
        status=Reservation.Status.CONFIRMED,
    ).exclude(pk=reservation.pk).exists():
        raise ReservationError("The selected resource is already confirmed for that date.")

    reservation.status = Reservation.Status.CONFIRMED
    try:
        reservation.save(update_fields=["status", "updated_at"])
    except IntegrityError as exc:
        raise ReservationError("The selected resource is already confirmed for that date.") from exc

    notify_reservation_event("approved", reservation)
    return reservation


def current_user_reservations(user) -> QuerySet[Reservation]:
    return Reservation.objects.select_related("resource").filter(user=user)



