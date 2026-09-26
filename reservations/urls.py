from django.urls import path

from . import views

app_name = "reservations"

urlpatterns = [
    path("", views.availability, name="availability"),
    path("mine/", views.my_reservations, name="my_reservations"),
    path("approvals/", views.approvals, name="approvals"),
    path("approvals/<int:pk>/", views.decide_approval_view, name="decide_approval"),
    path("reservations/create/", views.create_reservation_view, name="create_reservation"),
    path("reservations/<int:pk>/confirm/", views.confirm_reservation_view, name="confirm_reservation"),
    path("reservations/<int:pk>/cancel/", views.cancel_reservation_view, name="cancel_reservation"),
]

