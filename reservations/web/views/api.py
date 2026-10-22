"""CP1 walking skeleton: create a reservation through JSON (README, "CP1 walking skeleton")."""

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from ...services import ReservationError, create_draft
from ..forms import ReservationCreationForm


@require_POST
def create_reservation_api(request: HttpRequest) -> JsonResponse:
    """``POST /reservations`` → ``201 {"reservation_id": ...}``; the reservation stays DRAFT (OP-01).

    Uses the session login like the rest of the app, so the CSRF check applies
    to browsers as usual.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Body must be JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Body must be a JSON object."}, status=400)

    form = ReservationCreationForm(payload)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    try:
        reservation = create_draft(
            user=request.user,
            resource=form.cleaned_data["resource_id"],
            reservation_date=form.cleaned_data["reservation_date"],
        )
    except ReservationError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse({"reservation_id": reservation.pk}, status=201)
