"""Availability — read model of free resources (only reads, never allocates)."""

from django.db.models import QuerySet

from ..models import Reservation, Resource


def active_resources() -> QuerySet[Resource]:
    return Resource.objects.filter(is_active=True)


def available_resources_for_date(reservation_date) -> QuerySet[Resource]:
    occupied_resource_ids = Reservation.objects.filter(
        reservation_date=reservation_date,
        status=Reservation.Status.CONFIRMED,
    ).values_list("resource_id", flat=True)
    return active_resources().exclude(pk__in=occupied_resource_ids)


def current_user_reservations(user) -> QuerySet[Reservation]:
    return Reservation.objects.select_related("resource").filter(user=user)
