from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from ...models import Reservation
from ...services import ReservationError, decide_approval, pending_approval_requests, user_can_approve


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
