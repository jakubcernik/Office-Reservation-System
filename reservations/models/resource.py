from django.db import models


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
