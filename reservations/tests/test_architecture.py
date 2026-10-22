"""Repeatable checks for the architecture rules accepted in C03.

C03/L2 requires one architecture rule to be protected by a repeatable check.
RULE-1 (lifecycle ownership) is that check; RULE-2 (notification isolation)
belongs to the same ADR-01 and is cheap to keep next to it.

See ``docs/c03-architecture.md`` (ADR-01, G2, L2).
"""

import ast
from pathlib import Path

from django.test import SimpleTestCase

APP_ROOT = Path(__file__).resolve().parent.parent

#: The only package allowed to change the Reservation lifecycle state (RULE-1).
LIFECYCLE_OWNER = Path("services")

#: The only module allowed to define notification delivery (RULE-2).
NOTIFICATION_OWNER = Path("integrations") / "notifications.py"

_EXCLUDED_DIRS = {"migrations", "__pycache__"}
_STATUS_MUTATING_METHODS = {"create", "update", "update_or_create", "bulk_update"}


def _all_modules():
    """Application .py files, without tests and migrations."""
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = path.relative_to(APP_ROOT)
        if any(part in _EXCLUDED_DIRS for part in rel.parts):
            continue
        if rel.parts[0].startswith("tests"):
            continue
        yield path


def _application_modules():
    """Application modules outside the lifecycle owner and the notification boundary."""
    for path in _all_modules():
        rel = path.relative_to(APP_ROOT)
        if rel.parts[0] == LIFECYCLE_OWNER.name or rel == NOTIFICATION_OWNER:
            continue
        yield path


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _status_mutations(tree):
    """Line numbers where a module changes Reservation.status or status=... in create/update."""
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            targets = []

        for target in targets:
            if isinstance(target, ast.Attribute) and target.attr == "status":
                violations.append((node.lineno, "assigns .status"))

        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _STATUS_MUTATING_METHODS:
                if any(keyword.arg == "status" for keyword in node.keywords):
                    violations.append((node.lineno, f"{node.func.attr}(status=...)"))
    return violations


class LifecycleOwnershipTests(SimpleTestCase):
    """RULE-1: only Reservation Management (services/) changes the lifecycle state."""

    def test_only_services_package_changes_reservation_status(self):
        violations = {}
        for path in _application_modules():
            found = _status_mutations(_parse(path))
            if found:
                violations[str(path.relative_to(APP_ROOT))] = found
        self.assertEqual(
            violations,
            {},
            "Only the reservations/services/ package may change Reservation.status, "
            f"but found: {violations}",
        )

    def test_lifecycle_owner_package_exists(self):
        self.assertTrue((APP_ROOT / LIFECYCLE_OWNER / "__init__.py").is_file())


class NotificationIsolationTests(SimpleTestCase):
    """RULE-2: notification delivery is defined only in the integration module."""

    def test_only_notifications_module_defines_delivery(self):
        definers = []
        for path in _all_modules():
            for node in ast.walk(_parse(path)):
                if isinstance(node, ast.FunctionDef) and node.name == "notify_reservation_event":
                    definers.append(str(path.relative_to(APP_ROOT)))
        self.assertEqual(
            definers,
            [str(NOTIFICATION_OWNER)],
            "notify_reservation_event must be defined only in "
            f"{NOTIFICATION_OWNER}, but found it in: {definers}",
        )
