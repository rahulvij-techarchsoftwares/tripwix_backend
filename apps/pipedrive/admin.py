from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import path, reverse

from apps.pipedrive.models import Deal, Organization, Person
from apps.pipedrive.tasks import task_progressive_countdown_deal_sync, task_sync_organizations, task_sync_persons


class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'pipedrive_id', 'created_at', 'updated_at')
    search_fields = ('name', 'pipedrive_id')
    list_filter = ('created_at', 'updated_at')

    def sync_organizations(self, request, *args, **kwargs):
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        task_sync_organizations.delay()
        self.message_user(request, 'Organization synced successfully')
        return HttpResponseRedirect(reverse(f'admin:{app_label}_{model_name}_changelist'))

    sync_organizations.short_description = 'Sync Organizations'

    def get_urls(self):
        urls = super().get_urls()
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path('sync-organizations/', self.sync_organizations, name=f'{app_label}_{model_name}_sync'),
        ]
        return custom_urls + urls


class DealAdmin(admin.ModelAdmin):
    list_display = ('title', 'organization', 'pipedrive_id', 'status', 'value', 'currency', 'created_at', 'updated_at')
    search_fields = ('title', 'organization__name', 'pipedrive_id')
    list_filter = ('status', 'currency', 'created_at', 'updated_at')

    def sync_deals(self, request, *args, **kwargs):
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        task_progressive_countdown_deal_sync.delay()
        self.message_user(request, 'Deals synced successfully')
        return HttpResponseRedirect(reverse(f'admin:{app_label}_{model_name}_changelist'))

    sync_deals.short_description = 'Sync Deals'

    def get_urls(self):
        urls = super().get_urls()
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path('sync-deals/', self.sync_deals, name=f'{app_label}_{model_name}_sync'),
        ]
        return custom_urls + urls


class PersonAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'pipedrive_id', 'organization', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'phone', 'pipedrive_id')
    list_filter = ('created_at', 'updated_at')

    def sync_persons(self, request, *args, **kwargs):
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        task_sync_persons.delay()
        self.message_user(request, 'Persons synced successfully')
        return HttpResponseRedirect(reverse(f'admin:{app_label}_{model_name}_changelist'))

    sync_persons.short_description = 'Sync Persons'

    def get_urls(self):
        urls = super().get_urls()
        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path('sync-persons/', self.sync_persons, name=f'{app_label}_{model_name}_sync'),
        ]
        return custom_urls + urls


admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Deal, DealAdmin)
admin.site.register(Person, PersonAdmin)
