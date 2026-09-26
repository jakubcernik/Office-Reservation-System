from django.conf import settings
from django.db import models
from django.db.models import Q


class Resource(models.Model):
    class ResourceType(models.TextChoices):
        DESK = "DESK", "Desk"
        PARKING_SPOT = "PARKING", "Parking spot"

    name = models.CharField(max_length=120)
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices)
    location = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(
        default=False,
        help_text="Reservations for this resource have to be approved by an office manager.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resource_type", "name"]

    def __str__(self) -> str:
        return f"{self.get_resource_type_display()} {self.name}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Waiting for approval"
        CONFIRMED = "CONFIRMED", "Confirmed"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations")
    resource = models.ForeignKey(Resource, on_delete=models.PROTECT, related_name="reservations")
    reservation_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reservation_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "reservation_date"],
                condition=Q(status="CONFIRMED"),
                name="unique_confirmed_resource_date",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "reservation_date", "status"]),
            models.Index(fields=["resource", "reservation_date", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.resource} - {self.reservation_date} ({self.status})"


