from django.contrib import admin

from .models import Activity, Experience, Inclusion


class InclusionInline(admin.TabularInline):
    model = Inclusion
    extra = 1


@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ('title', 'location', 'overview', 'activity')
    search_fields = ('title', 'description', 'location__name')
    list_filter = (
        'location',
        'activity',
    )
    readonly_fields = (
        'id',
        'slug',
    )
    inlines = [InclusionInline]


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    list_filter = ('name',)
    readonly_fields = ('id',)
