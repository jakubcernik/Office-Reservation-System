from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from reservations.models import Reservation, Resource
from reservations.services import confirm_reservation, create_draft

#: Demo resources that need an office manager's approval (change C02).
#: Every other demo resource keeps the flag off, so the default behaviour of
#: the application is unchanged and confirmations stay immediate.
APPROVAL_RESOURCES = (
    {
        "name": "VED-01",
        "resource_type": Resource.ResourceType.DESK,
        "location": "Ředitelské křídlo",
    },
    {
        "name": "P-VIP",
        "resource_type": Resource.ResourceType.PARKING_SPOT,
        "location": "Návštěvní vjezd",
    },
)


class Command(BaseCommand):
    help = "Seed the database with demo office resources and optional sample reservations."

    def add_arguments(self, parser):
        parser.add_argument("--desks", type=int, default=12, help="Number of desk resources to create.")
        parser.add_argument(
            "--parking-spots", type=int, default=6, help="Number of parking spot resources to create."
        )
        parser.add_argument(
            "--demo-user",
            type=str,
            default="",
            help="Optional username for creating sample reservations.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing demo resources before seeding them again.",
        )

    def handle(self, *args, **options):
        desks = options["desks"]
        parking_spots = options["parking_spots"]
        demo_user = options["demo_user"].strip()
        force = options["force"]
        demo_resource_names = [f"A{index:02d}" for index in range(1, desks + 1)] + [
            f"P{index:02d}" for index in range(1, parking_spots + 1)
        ] + [spec["name"] for spec in APPROVAL_RESOURCES]

        if force:
            Reservation.objects.filter(resource__name__in=demo_resource_names).delete()
            deleted_count, _ = Resource.objects.filter(name__in=demo_resource_names).delete()
            self.stdout.write(self.style.WARNING(f"Removed {deleted_count} existing demo resources."))

        created_resources = 0
        for index in range(1, desks + 1):
            _, created = Resource.objects.get_or_create(
                name=f"A{index:02d}",
                defaults={
                    "resource_type": Resource.ResourceType.DESK,
                    "location": "Open office",
                    "is_active": True,
                },
            )
            created_resources += int(created)

        for index in range(1, parking_spots + 1):
            _, created = Resource.objects.get_or_create(
                name=f"P{index:02d}",
                defaults={
                    "resource_type": Resource.ResourceType.PARKING_SPOT,
                    "location": "Garage",
                    "is_active": True,
                },
            )
            created_resources += int(created)

        for spec in APPROVAL_RESOURCES:
            _, created = Resource.objects.get_or_create(
                name=spec["name"],
                defaults={
                    "resource_type": spec["resource_type"],
                    "location": spec["location"],
                    "is_active": True,
                    "requires_approval": True,
                },
            )
            created_resources += int(created)

        self.stdout.write(self.style.SUCCESS(f"Seeded {created_resources} new resources."))

        if not demo_user:
            self.stdout.write("No demo user provided, skipping sample reservations.")
            return

        User = get_user_model()
        user = User.objects.filter(username=demo_user).first()
        if not user:
            self.stdout.write(self.style.WARNING(f"User '{demo_user}' not found, skipping sample reservations."))
            return

        today = timezone.localdate()
        tomorrow = today + timedelta(days=1)

        desk = Resource.objects.filter(resource_type=Resource.ResourceType.DESK, is_active=True).first()
        parking = Resource.objects.filter(resource_type=Resource.ResourceType.PARKING_SPOT, is_active=True).first()
        if not desk or not parking:
            self.stdout.write(self.style.WARNING("Not enough resources to create sample reservations."))
            return

        if not Reservation.objects.filter(user=user, resource=desk, reservation_date=today, status=Reservation.Status.CONFIRMED).exists():
            desk_draft = create_draft(user=user, resource=desk, reservation_date=today)
            confirm_reservation(desk_draft)

        if not Reservation.objects.filter(user=user, resource=parking, reservation_date=today, status=Reservation.Status.CONFIRMED).exists():
            parking_draft = create_draft(user=user, resource=parking, reservation_date=today)
            confirm_reservation(parking_draft)

        if not Reservation.objects.filter(user=user, resource=desk, reservation_date=tomorrow, status=Reservation.Status.DRAFT).exists():
            create_draft(user=user, resource=desk, reservation_date=tomorrow)

        self.stdout.write(self.style.SUCCESS(f"Created sample reservations for user '{demo_user}'."))



