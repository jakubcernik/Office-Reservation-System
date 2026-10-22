"""Allocation rules checked before a reservation takes a resource.

Confirming a reservation and approving a request both allocate the resource,
so both run exactly these checks (BR-07). The module only reads; changing the
state stays with the lifecycle and approval modules.
"""

from ..models import Reservation, Resource
from .errors import ReservationError


def user_has_confirmed_desk(user, reservation_date) -> bool:
    return Reservation.objects.filter(
        user=user,
        reservation_date=reservation_date,
        resource__resource_type=Resource.ResourceType.DESK,
        status=Reservation.Status.CONFIRMED,
    ).exists()


def ensure_can_allocate(reservation: Reservation) -> None:
    """Raise ``ReservationError`` when the resource cannot be given to the reservation.

    Checks, in this order: the resource is active, parking has a confirmed desk
    for the same user and day (BR-04), and no other reservation holds the
    resource for that day (BR-02).
    """
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
