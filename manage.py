#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "office_reservation_system.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - startup guard
        raise ImportError(
            "Couldn't import Django. Did you install the dependencies?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

