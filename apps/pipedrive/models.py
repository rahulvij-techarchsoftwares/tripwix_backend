from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import CreatedUpdatedAbstractMixin

User = get_user_model()


class Person(CreatedUpdatedAbstractMixin):
    pipedrive_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    pipedrive_metadata = models.JSONField(null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class Organization(CreatedUpdatedAbstractMixin):
    pipedrive_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    pipedrive_metadata = models.JSONField(null=True, blank=True)
    deal_offset = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["pipedrive_id"], name="organization_pipedrive_id_idx"),
        ]

    def __str__(self):
        return self.name


class Deal(CreatedUpdatedAbstractMixin):
    organization = models.ForeignKey('Organization', on_delete=models.SET_NULL, null=True, blank=True)
    pipedrive_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=255, blank=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    currency = models.CharField(max_length=3, blank=True)
    pipedrive_metadata = models.JSONField(null=True)
    checkin_date = models.DateField(null=True, blank=True)
    checkout_date = models.DateField(null=True, blank=True)
    number_of_guests = models.PositiveIntegerField(null=True, blank=True)
    property_id = models.CharField(max_length=255, blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    destination = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    lead_source = models.CharField(max_length=255, blank=True)
    budget = models.CharField(max_length=50, blank=True)
    property_type = models.CharField(max_length=50, blank=True)
    requested_nights = models.PositiveIntegerField(null=True, blank=True)
    flexible_dates = models.BooleanField(default=False)
    property_name = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["pipedrive_id"], name="deal_pipedrive_id_idx"),
        ]

    def __str__(self):
        return f'{self.title} - {self.value}, {self.currency}'
