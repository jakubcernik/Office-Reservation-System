from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import AvailabilityForm, DraftCreationForm, RegistrationForm
from .models import Reservation
from .services import (
    ReservationError,
    available_resources_for_date,
    cancel_reservation,
    confirm_reservation,
    create_draft,
    current_user_reservations,
)


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("reservations:availability")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("reservations:availability")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def availability(request: HttpRequest) -> HttpResponse:
    form = AvailabilityForm(request.GET or None)
    if form.is_valid():
        reservation_date = form.cleaned_data["reservation_date"]
    else:
        reservation_date = timezone.localdate()

    available_resources = available_resources_for_date(reservation_date)
    resources = [
        {
            "resource": resource,
            "draft_form": DraftCreationForm(
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
    }
    return render(request, "reservations/availability.html", context)


@login_required
def create_draft_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    form = DraftCreationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the highlighted errors.")
        return redirect(_availability_url_for_form(form))

    resource = form.cleaned_data["resource_id"]
    reservation_date = form.cleaned_data["reservation_date"]
    try:
        create_draft(user=request.user, resource=resource, reservation_date=reservation_date)
        messages.success(request, f"Draft reservation created for {resource} on {reservation_date}.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("reservations:availability") + f"?date={reservation_date}")


@login_required
def my_reservations(request: HttpRequest) -> HttpResponse:
    reservations = current_user_reservations(request.user)
    return render(request, "reservations/my_reservations.html", {"reservations": reservations})


@login_required
def confirm_reservation_view(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reservation = get_object_or_404(Reservation.objects.select_related("resource", "user"), pk=pk)
    if reservation.user_id != request.user.id:
        return HttpResponseForbidden("You can only confirm your own reservations.")

    try:
        confirm_reservation(reservation)
        messages.success(request, "Reservation confirmed.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return redirect("reservations:my_reservations")


@login_required
def cancel_reservation_view(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    reservation = get_object_or_404(Reservation.objects.select_related("resource", "user"), pk=pk)
    try:
        cancel_reservation(reservation, actor=request.user)
        messages.success(request, "Reservation cancelled.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return redirect("reservations:my_reservations")


def _availability_url_for_form(form: DraftCreationForm) -> str:
    reservation_date = form.data.get("reservation_date") or form.initial.get("reservation_date")
    if reservation_date:
        return reverse("reservations:availability") + f"?date={reservation_date}"
    return reverse("reservations:availability")


