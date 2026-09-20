from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Resource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                (
                    "resource_type",
                    models.CharField(
                        choices=[("DESK", "Desk"), ("PARKING", "Parking spot")],
                        max_length=20,
                    ),
                ),
                ("location", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["resource_type", "name"],
            },
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reservation_date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[("DRAFT", "Draft"), ("CONFIRMED", "Confirmed"), ("CANCELLED", "Cancelled")],
                        default="DRAFT",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "resource",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservations", to="reservations.resource"),
                ),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reservations", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["-reservation_date", "-created_at"],
                "indexes": [
                    models.Index(fields=["user", "reservation_date", "status"], name="reservations_user_rese_7f7dfd_idx"),
                    models.Index(fields=["resource", "reservation_date", "status"], name="reservations_resourc_62c6a8_idx"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="reservation",
            constraint=models.UniqueConstraint(
                condition=Q(status="CONFIRMED"),
                fields=["resource", "reservation_date"],
                name="unique_confirmed_resource_date",
            ),
        ),
    ]


