"""C04 measurement: concurrent reservations of one resource (quality concern Q-1).

Criterion (see "C04 — Quality & Measurement" in docs/evidence-and-evolution.md):
in every one of ROUNDS rounds, ATTEMPTS users press Reserve for the same
resource and day at the same moment (a barrier releases all threads at once).
The round passes when exactly one reservation ends CONFIRMED, every other
attempt ends with ReservationError, and no DRAFT or second CONFIRMED is left.
Refusals are reported split by who stopped them (rule check or DB index), which
shows whether the attempts really overlapped.

The declared context is PostgreSQL, the production database. Run it there with

    TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54329/postgres \
        python manage.py test reservations.tests.test_quality_concurrency

On SQLite (the default test database) the test is skipped: SQLite serialises
writers with a file lock, so it measures a different system.
"""

import threading
import time
from collections import Counter
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from ..models import Reservation, Resource
from ..services import ReservationError, create_reservation

ATTEMPTS = 20
ROUNDS = 10


def _run_round(users, resource, reservation_date):
    barrier = threading.Barrier(len(users))
    outcomes = []
    lock = threading.Lock()

    def attempt(user):
        try:
            # Connect before the barrier, otherwise opening the connection
            # staggers the threads and they never meet at the critical point.
            connection.ensure_connection()
            barrier.wait()
            create_reservation(user=user, resource=resource, reservation_date=reservation_date)
            result = "confirmed"
        except ReservationError as exc:
            # Who stopped the attempt: the rule check in the service, or the
            # database index when the check was passed at the same moment.
            result = "refused_by_index" if isinstance(exc.__cause__, IntegrityError) else "refused_by_check"
        except Exception as exc:  # anything else breaks the criterion
            result = f"error:{type(exc).__name__}"
        finally:
            connections.close_all()
        with lock:
            outcomes.append(result)

    threads = [threading.Thread(target=attempt, args=(user,)) for user in users]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return Counter(outcomes), time.perf_counter() - started


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentReservationMeasurement(TransactionTestCase):
    """Q-1 measurement; skipped on SQLite, which has no row locking."""

    def test_one_winner_per_resource_and_day(self):
        users = [
            get_user_model().objects.create_user(username=f"user{index}", password="password12345")
            for index in range(ATTEMPTS)
        ]
        resource = Resource.objects.create(name="A01", resource_type=Resource.ResourceType.DESK)
        first_day = date.today() + timedelta(days=30)

        rounds = []
        for round_index in range(ROUNDS):
            reservation_date = first_day + timedelta(days=round_index)
            outcomes, seconds = _run_round(users, resource, reservation_date)
            stored = Counter(
                Reservation.objects.filter(resource=resource, reservation_date=reservation_date).values_list(
                    "status", flat=True
                )
            )
            rounds.append((round_index + 1, outcomes, stored, seconds))

        print(f"\nC04 Q-1 on {connection.vendor} {connection.pg_version if connection.vendor == 'postgresql' else ''}")
        print(f"attempts per round: {ATTEMPTS}, rounds: {ROUNDS}")
        for number, outcomes, stored, seconds in rounds:
            print(f"round {number:2d}: outcomes={dict(outcomes)} stored={dict(stored)} time={seconds * 1000:.0f} ms")

        for number, outcomes, stored, _ in rounds:
            with self.subTest(round=number):
                refused = outcomes["refused_by_check"] + outcomes["refused_by_index"]
                self.assertEqual(outcomes["confirmed"], 1)
                self.assertEqual(refused, ATTEMPTS - 1, f"unexpected outcomes: {dict(outcomes)}")
                self.assertEqual(stored, Counter({Reservation.Status.CONFIRMED: 1}))
