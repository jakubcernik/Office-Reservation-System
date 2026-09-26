from django.contrib import admin

from .models import Reservation, Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "resource_type", "location", "is_active", "requires_approval")
    list_filter = ("resource_type", "is_active", "requires_approval")
    search_fields = ("name", "location")
    ordering = ("resource_type", "name")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("user", "resource", "reservation_date", "status", "created_at")
    list_filter = ("status", "reservation_date", "resource__resource_type")
    search_fields = ("user__username", "user__first_name", "user__last_name", "resource__name")
    autocomplete_fields = ("user", "resource")
    date_hierarchy = "reservation_date"

