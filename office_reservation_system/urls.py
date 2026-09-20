from django.contrib import admin
from django.urls import include, path

from reservations import views as reservation_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/register/", reservation_views.register, name="register"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("reservations.urls")),
]

