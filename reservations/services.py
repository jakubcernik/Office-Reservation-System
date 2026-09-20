import logging

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from .models import Reservation, Resource

logger = logging.getLogger(__name__)


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


def create_draft(*, user, resource: Resource, reservation_date) -> Reservation:
    if not resource.is_active:
        raise ReservationError("Selected resource is not active.")

    return Reservation.objects.create(
        user=user,
        resource=resource,
        reservation_date=reservation_date,
        status=Reservation.Status.DRAFT,
    )


def user_has_confirmed_desk(user, reservation_date) -> bool:
    return Reservation.objects.filter(
        user=user,
        reservation_date=reservation_date,
        resource__resource_type=Resource.ResourceType.DESK,
        status=Reservation.Status.CONFIRMED,
    ).exists()


@transaction.atomic
def confirm_reservation(reservation: Reservation) -> Reservation:
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

    reservation.status = Reservation.Status.CONFIRMED
    try:
        reservation.save(update_fields=["status", "updated_at"])
    except IntegrityError as exc:
        raise ReservationError("The selected resource is already confirmed for that date.") from exc

    notify_reservation_event("confirmed", reservation)
    return reservation


@transaction.atomic
def cancel_reservation(reservation: Reservation, *, actor) -> Reservation:
    reservation = Reservation.objects.select_for_update().select_related("user").get(pk=reservation.pk)

    if reservation.user_id != actor.id:
        raise ReservationError("You can only cancel your own reservation.")

    if reservation.status != Reservation.Status.CONFIRMED:
        raise ReservationError("Only confirmed reservations can be cancelled.")

    reservation.status = Reservation.Status.CANCELLED
    reservation.save(update_fields=["status", "updated_at"])
    notify_reservation_event("cancelled", reservation)
    return reservation


def current_user_reservations(user) -> QuerySet[Reservation]:
    return Reservation.objects.select_related("resource").filter(user=user)



