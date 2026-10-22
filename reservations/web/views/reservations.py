from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from ...availability import current_user_reservations
from ...models import Reservation
from ...services import (
    ReservationError,
    cancel_reservation,
    confirm_reservation,
    create_reservation,
    expire_stale_approvals,
)
from ..forms import ReservationCreationForm


@login_required
def create_reservation_view(request: HttpRequest) -> HttpResponse:
    """Reserve a resource with a single action.

    Creating and confirming are one user action: the reservation is stored and
    the allocation rules are applied together, so the user never has to deal
    with a draft (v0.3 flow).
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    form = ReservationCreationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the highlighted errors.")
        return redirect(_availability_url_for_form(form))

    resource = form.cleaned_data["resource_id"]
    reservation_date = form.cleaned_data["reservation_date"]
    try:
        reservation = create_reservation(user=request.user, resource=resource, reservation_date=reservation_date)
        if reservation.status == Reservation.Status.PENDING_APPROVAL:
            messages.success(
                request, f"{resource} requested for {reservation_date}. Waiting for an office manager."
            )
        else:
            messages.success(request, f"{resource} reserved for {reservation_date}.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("reservations:availability") + f"?date={reservation_date}")


@login_required
def my_reservations(request: HttpRequest) -> HttpResponse:
    expire_stale_approvals()
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
        updated = confirm_reservation(reservation)
        if updated.status == Reservation.Status.PENDING_APPROVAL:
            messages.success(request, "Reservation sent for approval.")
        else:
            messages.success(request, "Reservation confirmed.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return _redirect_after_action(request, "reservations:my_reservations")


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
    return _redirect_after_action(request, "reservations:my_reservations")


def _redirect_after_action(request: HttpRequest, fallback: str) -> HttpResponse:
    """Return to the page the action was started from, when that is safe.

    The availability page offers the same buttons as My reservations, so the
    user does not have to leave the page to confirm a draft.
    """
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect(fallback)


def _availability_url_for_form(form: ReservationCreationForm) -> str:
    reservation_date = form.data.get("reservation_date") or form.initial.get("reservation_date")
    if reservation_date:
        return reverse("reservations:availability") + f"?date={reservation_date}"
    return reverse("reservations:availability")
