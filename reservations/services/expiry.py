import logging

from django.utils import timezone

from ..models import Reservation

logger = logging.getLogger(__name__)


def expire_stale_approvals() -> int:
    """Move requests nobody decided in time to EXPIRED (BR-06).

    A request expires once the day it was made for is over, so the check is a
    plain comparison with today. It runs whenever reservations are read or
    changed, which is why the system needs no background job.
    """
    expired_count = Reservation.objects.filter(
        status=Reservation.Status.PENDING_APPROVAL,
        reservation_date__lt=timezone.localdate(),
    ).update(status=Reservation.Status.EXPIRED, updated_at=timezone.now())
    if expired_count:
        logger.info("Expired %s pending approval request(s).", expired_count)
    return expired_count
