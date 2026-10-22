from django.db import transaction
from django.db.models import QuerySet

from ..models import Reservation
from .errors import ReservationError
from .expiry import expire_stale_approvals
from .lifecycle import allocate, notify_after_commit
from .permissions import user_can_approve
from .rules import ensure_can_allocate


def pending_approval_requests() -> QuerySet[Reservation]:
    """Requests waiting for a decision, oldest reservation day first."""
    expire_stale_approvals()
    return (
        Reservation.objects.select_related("resource", "user")
        .filter(status=Reservation.Status.PENDING_APPROVAL)
        .order_by("reservation_date", "resource__name")
    )


def decide_approval(reservation: Reservation, *, actor, approve: bool) -> Reservation:
    """Office manager decides about a request waiting for approval (OP-05).

    Approving allocates the resource, so the rules are checked again: the world
    may have changed since the request was created (BR-07).
    """
    if not user_can_approve(actor):
        raise ReservationError("Only an office manager can decide about approval requests.")

    # Expiry is bookkeeping, not part of the decision, so it runs outside the
    # transaction below: a request that ran out of time has to stay expired even
    # when the decision itself is refused.
    expire_stale_approvals()
    return _apply_approval_decision(reservation, approve=approve)


@transaction.atomic
def _apply_approval_decision(reservation: Reservation, *, approve: bool) -> Reservation:
    reservation = Reservation.objects.select_for_update().select_related("resource", "user").get(pk=reservation.pk)

    if reservation.status != Reservation.Status.PENDING_APPROVAL:
        raise ReservationError("Only a reservation waiting for approval can be decided.")

    if not approve:
        reservation.status = Reservation.Status.REJECTED
        reservation.save(update_fields=["status", "updated_at"])
        notify_after_commit("rejected", reservation)
        return reservation

    ensure_can_allocate(reservation)
    allocate(reservation)
    notify_after_commit("approved", reservation)
    return reservation
