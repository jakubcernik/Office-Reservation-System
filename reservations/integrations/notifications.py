"""Notification Integration — the boundary for reservation notifications.

This module is the only place that talks to the outside world about a
reservation event (ADR-01 / G2 in ``docs/c03-architecture.md``). The
reservation outcome must never depend on whether delivery succeeds, so a
failure is logged and swallowed here and retry belongs to this boundary.
"""

import logging

from ..models import Reservation

logger = logging.getLogger(__name__)


def notify_reservation_event(action: str, reservation: Reservation) -> bool:
    """Deliver a reservation event best-effort.

    Returns ``True`` when the event reached the transport and ``False`` when
    delivery failed. Callers must ignore the result: a failed notification may
    not change the reservation state.
    """
    try:
        _send(action, reservation)
    except Exception:
        logger.exception(
            "Notification delivery failed action=%s reservation id=%s",
            action,
            reservation.pk,
        )
        return False
    return True


def _send(action: str, reservation: Reservation) -> None:
    # The real Notification Service is not wired up yet; local development
    # writes the event to the log instead.
    logger.info(
        "%s reservation id=%s user=%s resource=%s date=%s status=%s",
        action,
        reservation.pk,
        reservation.user_id,
        reservation.resource_id,
        reservation.reservation_date,
        reservation.status,
    )
