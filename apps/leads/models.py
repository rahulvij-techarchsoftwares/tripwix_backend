from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import AbstractCreatedDateMixin


class Lead(AbstractCreatedDateMixin):
    HOW_CAN_WE_HELP_CHOICES = [
        ('villa_rental', "I'm interested in a Villa Rental"),
        ('property_management', 'I would like to know more about property management'),
        ('homeowner_partner', 'I am a homeowner and would like to partner with you'),
        ('travel_agent_inquiry', 'I am a travel agent with an inquiry'),
        ('book_services', 'Would like to book extra services and/or activities'),
        ('press_member_info', 'I am a Press Member and desire information on the company'),
        ('other', 'Other (specify the service)'),
    ]

    WHERE_HEARD_CHOICES = [
        ('traveled_before', 'I have traveled with you before'),
        ('word_of_mouth', 'Word of mouth'),
        ('referral', 'Referral'),
        ('search_engine', 'Search (Google, Bing, etc)'),
        ('online_advertising', 'Online Advertising'),
        ('influencer', 'Influencer'),
        ('magazine_advert', 'Advert on Magazine'),
        ('event', 'Event'),
        ('social_media', 'Social Media'),
        ('travel_agency', 'Travel Agency'),
        ('other', 'Other (please specify)'),
    ]

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    desired_destination = models.CharField(max_length=255, blank=True, null=True)
    how_can_we_help = models.CharField(max_length=255, choices=HOW_CAN_WE_HELP_CHOICES, blank=True, null=True)
    how_can_we_help_extra_field = models.TextField(blank=True, null=True)
    where_heard_about_us = models.CharField(max_length=255, choices=WHERE_HEARD_CHOICES, blank=True, null=True)
    where_heard_about_us_extra_field = models.CharField(max_length=255, blank=True, null=True)
    questions_or_comments = models.TextField(blank=True, null=True)
    src_id = models.IntegerField(blank=True, null=True)
    form_id = models.IntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    newsletter = models.BooleanField(default=False, blank=True, null=True)
    smsMarketing = models.BooleanField(default=False, blank=True, null=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"

    def clean(self):
        if self.where_heard_about_us == 'others' and not self.where_heard_about_us_extra_field:
            raise ValidationError(
                {
                    'where_heard_about_us_extra_field': 'This field is required when "Others" is selected in "Where heard about us".'
                }
            )
        if self.how_can_we_help == 'others' and not self.how_can_we_help_extra_field:
            raise ValidationError(
                {
                    'how_can_we_help_extra_field': 'This field is required when "Others" is selected in "How can we help".'
                }
            )

    def create_lead(self):
        from apps.pipedrive.tasks import task_send_lead_to_pipedrive

        if settings.SEND_DATA_TO_PIPEDRIVE:
            task_send_lead_to_pipedrive.apply_async((self.id,), countdown=5)
        else:
            print("unable to send payload to inquiry- LOCAL/TEST ")

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_lead()


class Inquiry(AbstractCreatedDateMixin):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    checkin_date = models.DateField()
    checkout_date = models.DateField()
    number_of_bedrooms = models.PositiveIntegerField()
    number_of_guests = models.PositiveIntegerField()
    note = models.TextField(blank=True, null=True)
    is_travel_date_flexible = models.BooleanField(default=False)
    property_id = models.CharField(max_length=255, blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)
    smsMarketing = models.BooleanField(default=False, null=True, blank=True)

    class Meta:
        verbose_name = 'Inquiry'
        verbose_name_plural = 'Inquiries'

    def __str__(self):
        return f"Inquiry from {self.first_name} {self.last_name} ({self.email})"

    def create_inquiry(self):
        from apps.pipedrive.tasks import task_process_inquiry_create

        if settings.SEND_DATA_TO_PIPEDRIVE:
            task_process_inquiry_create.apply_async((self.id,), countdown=5)
        else:
            print("unable to send payload to inquiry- LOCAL/TEST ")

    def save(self, *args, **kwargs):
        create_inquiry = False
        if self.pk is None:
            create_inquiry = True

        super().save(*args, **kwargs)
        if create_inquiry:
            self.create_inquiry()
