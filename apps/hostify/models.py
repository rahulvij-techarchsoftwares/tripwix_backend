from django.db import models

from apps.core.models import CreatedUpdatedAbstractMixin
from apps.hostify.constants import CalendarStatusChoices, ReservationStatusChoices
from apps.properties.models import Property


class PropertyCalendar(CreatedUpdatedAbstractMixin):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='hostify_calendars')
    date = models.DateField()
    hostify_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=CalendarStatusChoices.choices, default=CalendarStatusChoices.AVAILABLE
    )
    reservation_status = models.CharField(
        max_length=20, choices=ReservationStatusChoices.choices, default=ReservationStatusChoices.NO_STATUS
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('property', 'date')
