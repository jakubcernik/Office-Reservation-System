from django.contrib import messages
from django.contrib.auth import login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from ..forms import RegistrationForm


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("reservations:availability")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("reservations:availability")
    else:
        form = RegistrationForm()

    return render(request, "registration/register.html", {"form": form})
