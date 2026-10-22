from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from ...availability import (
    VIEWBOX,
    active_resources,
    available_resources_for_date,
    current_user_reservations,
    floor_plan_spots,
)
from ...services import expire_stale_approvals
from ..forms import AvailabilityForm, ReservationCreationForm


@login_required
def availability(request: HttpRequest) -> HttpResponse:
    # Requests that were never decided expire when their reservation day ends.
    expire_stale_approvals()

    form = AvailabilityForm(request.GET or None)
    if form.is_valid():
        reservation_date = form.cleaned_data["reservation_date"]
    else:
        reservation_date = timezone.localdate()

    available_resources = available_resources_for_date(reservation_date)
    resources = [
        {
            "resource": resource,
            "reservation_form": ReservationCreationForm(
                initial={"resource_id": resource.pk, "reservation_date": reservation_date}
            ),
        }
        for resource in available_resources
    ]
    user_reservations = current_user_reservations(request.user).filter(reservation_date=reservation_date)

    context = {
        "date_form": form if form.is_valid() else AvailabilityForm(initial={"reservation_date": reservation_date}),
        "selected_date": reservation_date,
        "available_resources": resources,
        "user_reservations": user_reservations,
        "floor_plan_spots": floor_plan_spots(
            active_resources(),
            [resource.pk for resource in available_resources],
            user_reservations,
        ),
        "floor_plan_viewbox": f"0 0 {VIEWBOX[0]} {VIEWBOX[1]}",
    }
    return render(request, "reservations/availability.html", context)
