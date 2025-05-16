from django.contrib import admin
from django.db import models

from apps.experiences.models import Experience
from apps.properties.widgets import SimpleSelectizeMultipleWidget

from .models import City, Country, CountryVatRate, District, Location, Region, SubLocation


class CountryVatRateInline(admin.TabularInline):
    model = CountryVatRate
    extra = 0


class LocationAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = (
        'name',
        'country',
        'region',
        'district',
        'is_active',
        'active_sublocations',
        'sort_order',
        'related_experiences',
    )
    list_editable = ('sort_order',)
    ordering = ('sort_order',)

    formfield_overrides = {
        models.ManyToManyField: {"widget": SimpleSelectizeMultipleWidget},
    }

    def related_experiences(self, obj):
        return ", ".join([experience.title for experience in Experience.objects.filter(location=obj)])

    related_experiences.short_description = 'Experiences'

    fieldsets = (
        (
            None,
            {
                'fields': ('name', 'slug', 'is_active', 'active_sublocations', 'sort_order', 'banner'),
                'description': 'Write the name and other basic details of the location.',
            },
        ),
        (
            'Relative Location',
            {
                'classes': ('settings',),
                'fields': (
                    'cities',
                    ('country', 'region', 'district'),
                ),
                'description': 'Set the related city, country, region, and district.',
            },
        ),
        (
            'Guide Information',
            {
                'classes': ('collapse',),
                'fields': ('guide_description', 'when_to_leave', 'how_to_get_there', 'good_to_know'),
                'description': 'Provide information to guide visitors.',
            },
        ),
    )

    class Media:
        js = (
            '/static/js/force_jquery.js',
            '/static/js/tabbed_translation_fields.js',
        )
        css = {
            'screen': ('/static/css/tabbed_translation_fields.css',),
        }


class CountryAdmin(admin.ModelAdmin):
    inlines = [CountryVatRateInline]


class SubLocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'image')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('image',)


class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'country__name')
    list_select_related = ('country',)
    list_filter = ('country',)
    ordering = ('name',)


admin.site.register(Location, LocationAdmin)
admin.site.register(SubLocation, SubLocationAdmin)
admin.site.register(Country, CountryAdmin)
admin.site.register(City, CityAdmin)
admin.site.register(Region)
admin.site.register(District)
