from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Reservation, Resource


class AvailabilityForm(forms.Form):
    reservation_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date",
    )


class ReservationCreationForm(forms.Form):
    resource_id = forms.IntegerField(widget=forms.HiddenInput)
    reservation_date = forms.DateField(widget=forms.HiddenInput)

    def clean_resource_id(self):
        resource_id = self.cleaned_data["resource_id"]
        try:
            return Resource.objects.get(pk=resource_id)
        except Resource.DoesNotExist as exc:
            raise forms.ValidationError("Selected resource does not exist.") from exc

    def clean(self):
        cleaned_data = super().clean()
        resource = cleaned_data.get("resource_id")
        reservation_date = cleaned_data.get("reservation_date")
        if resource and reservation_date and not resource.is_active:
            raise forms.ValidationError("Selected resource is not active.")
        return cleaned_data


class ReservationActionForm(forms.Form):
    reservation_id = forms.IntegerField(widget=forms.HiddenInput)

    def clean_reservation_id(self):
        reservation_id = self.cleaned_data["reservation_id"]
        try:
            return Reservation.objects.get(pk=reservation_id)
        except Reservation.DoesNotExist as exc:
            raise forms.ValidationError("Selected reservation does not exist.") from exc


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def save(self, commit: bool = True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


