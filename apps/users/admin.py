from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from apps.users.models import UserProfile, WebsiteUser

User = get_user_model()
admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class BaseUserAdmin(UserAdmin):
    """
    Base UserAdmin class to be used for all user models.
    """

    inlines = (UserProfileInline,)
    readonly_fields = ("date_joined", "last_login")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj=obj)
        if not request.user.has_perms(['auth.change_user']):
            readonly_fields += ("groups", "user_permissions", "is_superuser", "is_staff", "is_active")
        return readonly_fields


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom admin to allow users to edit their own profile without having to have the change_user permission.

    Users without the change_user permission will not be able to change:
        groups, user_permissions, is_superuser, or is_staff fields.
    """

    add_fieldsets = (
        (
            'Credentials',
            {
                'classes': ('wide',),
                'fields': ('username', 'password1', 'password2'),
            },
        ),
        (
            'Permissions',
            {
                'classes': ('wide',),
                'fields': ('is_staff', 'is_active'),
            },
        ),
    )

    def has_change_permission(self, request, obj=None):
        if obj == request.user:
            return True
        return super().has_change_permission(request, obj)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=True)


@admin.register(WebsiteUser)
class WebsiteUserAdmin(BaseUserAdmin):
    """
    Custom admin for WebsiteUser model.
    """

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_staff=False)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=...):
        return False
