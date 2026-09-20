from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("", views.availability, name="availability"),
    path("mine/", views.my_reservations, name="my_reservations"),
    path("drafts/create/", views.create_draft_view, name="create_draft"),
    path("reservations/<int:pk>/confirm/", views.confirm_reservation_view, name="confirm_reservation"),
    path("reservations/<int:pk>/cancel/", views.cancel_reservation_view, name="cancel_reservation"),
]

