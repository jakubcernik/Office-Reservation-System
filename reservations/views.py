from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import AvailabilityForm, RegistrationForm, ReservationCreationForm
from .models import Reservation
from .services import (
    ReservationError,
    available_resources_for_date,
    cancel_reservation,
    confirm_reservation,
    create_reservation,
    current_user_reservations,
    decide_approval,
    expire_stale_approvals,
    pending_approval_requests,
    user_can_approve,
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
    }
    return render(request, "reservations/availability.html", context)


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
def approvals(request: HttpRequest) -> HttpResponse:
    if not user_can_approve(request.user):
        return HttpResponseForbidden("Only an office manager can decide about approval requests.")

    return render(
        request,
        "reservations/approvals.html",
        {"pending_requests": pending_approval_requests()},
    )


@login_required
def decide_approval_view(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    if not user_can_approve(request.user):
        return HttpResponseForbidden("Only an office manager can decide about approval requests.")

    decision = request.POST.get("decision")
    if decision not in {"approve", "reject"}:
        messages.error(request, "Unknown decision.")
        return redirect("reservations:approvals")

    reservation = get_object_or_404(Reservation.objects.select_related("resource", "user"), pk=pk)
    try:
        decide_approval(reservation, actor=request.user, approve=decision == "approve")
        messages.success(request, "Request approved." if decision == "approve" else "Request rejected.")
    except ReservationError as exc:
        messages.error(request, str(exc))
    return redirect("reservations:approvals")


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


