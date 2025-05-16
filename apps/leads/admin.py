from django.contrib import admin
from django.urls import reverse_lazy
from django.utils.html import format_html

from apps.properties.models import Property

from .models import Inquiry, Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'desired_destination', 'created_at')
    search_fields = ('first_name', 'last_name', 'email')
    list_filter = ('desired_destination', 'created_at')
    readonly_fields = (
        'first_name',
        'last_name',
        'email',
        'phone_number',
        'desired_destination',
        'how_can_we_help',
        'where_heard_about_us',
        'questions_or_comments',
        'newsletter',
        'how_can_we_help_extra_field',
        'where_heard_about_us_extra_field',
        'get_property_info',
        'form_id',
    )

    fieldsets = (
        (
            'Basic Information',
            {
                'fields': ('first_name', 'last_name', 'email', 'phone_number'),
                'description': 'Basic contact information for the lead.',
            },
        ),
        (
            'Additional Information',
            {
                'fields': (
                    'desired_destination',
                    'how_can_we_help',
                    'where_heard_about_us',
                    'questions_or_comments',
                    'notes',
                    'newsletter',
                    'how_can_we_help_extra_field',
                    'where_heard_about_us_extra_field',
                ),
                'description': 'Details and notes for this lead.',
            },
        ),
        (
            'Source Information',
            {
                'fields': ('get_property_info', 'form_id'),
                'description': 'Page and form IDs related to the lead.',
            },
        ),
    )

    def get_property_info(self, obj):
        if obj.src_id:
            property = Property.objects.filter(id=obj.src_id).first()
            property_admin_change_url = f'admin:{Property._meta.app_label}_{Property._meta.model_name}_change'
            return format_html(
                f'<a href="{reverse_lazy(property_admin_change_url, args=(property.id,))}">{property}</a>'
            )
        return None

    get_property_info.short_description = 'Property'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'checkin_date', 'checkout_date', 'is_travel_date_flexible')
    search_fields = ('first_name', 'last_name', 'email')
    list_filter = ('is_travel_date_flexible', 'checkin_date', 'checkout_date')
    readonly_fields = (
        'first_name',
        'last_name',
        'email',
        'phone_number',
        'checkin_date',
        'checkout_date',
        'number_of_bedrooms',
        'number_of_guests',
        'is_travel_date_flexible',
        'get_property_info',
        'source_url',
        'smsMarketing',
    )

    fieldsets = (
        (
            'Basic Information',
            {
                'fields': ('first_name', 'last_name', 'email', 'phone_number'),
                'description': 'Basic contact information for the lead.',
            },
        ),
        (
            'Additional Information',
            {
                'fields': (
                    'checkin_date',
                    'checkout_date',
                    'number_of_bedrooms',
                    'number_of_guests',
                    'note',
                    'is_travel_date_flexible',
                    'smsMarketing',
                ),
                'description': 'Details and notes for this lead.',
            },
        ),
        (
            'Source Information',
            {
                'fields': ('get_property_info', 'source_url'),
                'description': 'Page or property related to the lead.',
            },
        ),
    )

    def get_property_info(self, obj):
        if obj.property_id:
            property = Property.objects.filter(id=obj.property_id).first()
            property_admin_change_url = f'admin:{Property._meta.app_label}_{Property._meta.model_name}_change'
            return format_html(
                f'<a href="{reverse_lazy(property_admin_change_url, args=(property.id,))}">{property}</a>'
            )
        return None

    get_property_info.short_description = 'Property'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
