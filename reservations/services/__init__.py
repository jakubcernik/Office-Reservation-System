"""Service layer — the only owner of Reservation lifecycle changes.

Every change of ``Reservation.status`` lives in this package (RULE-1, ADR-01 in
``docs/c03-architecture.md``). Controllers import from here, not from the modules.
"""

from .approvals import decide_approval, pending_approval_requests
from .availability import active_resources, available_resources_for_date, current_user_reservations
from .errors import ReservationError
from .expiry import expire_stale_approvals
from .floor_plan import VIEWBOX, floor_plan_spots
from .lifecycle import (
    CANCELLABLE_STATUSES,
    cancel_reservation,
    confirm_reservation,
    create_draft,
    create_reservation,
)
from .permissions import MANAGER_GROUP_NAME, user_can_approve
from .rules import ensure_can_allocate, user_has_confirmed_desk

__all__ = [
    "CANCELLABLE_STATUSES",
    "MANAGER_GROUP_NAME",
    "VIEWBOX",
    "ReservationError",
    "active_resources",
    "available_resources_for_date",
    "cancel_reservation",
    "confirm_reservation",
    "create_draft",
    "create_reservation",
    "current_user_reservations",
    "decide_approval",
    "ensure_can_allocate",
    "expire_stale_approvals",
    "floor_plan_spots",
    "pending_approval_requests",
    "user_can_approve",
    "user_has_confirmed_desk",
]
