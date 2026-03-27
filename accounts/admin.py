from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from accounts.models import AdminActionLog, Notification, ProfileChangeRequest, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("full_name", "organization")}),
        (_("Permissions"), {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {"classes": ("wide",), "fields": ("email", "full_name", "organization", "role", "password1", "password2")},
        ),
    )
    list_display = ("email", "full_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active")
    ordering = ("email",)
    search_fields = ("email", "full_name")

    def get_fieldsets(self, request, obj=None):
        return super().get_fieldsets(request, obj)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "created_at", "is_read", "profile_change_request")
    list_filter = ("is_read", "kind")
    search_fields = ("kind", "title", "body", "user__email")
    raw_id_fields = ("profile_change_request",)


@admin.register(ProfileChangeRequest)
class ProfileChangeRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "proposed_full_name", "status", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("user__email", "proposed_full_name")
    raw_id_fields = ("user", "reviewed_by")


@admin.register(AdminActionLog)
class AdminActionLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "method", "path", "ip")
    list_filter = ("method", "created_at")
    search_fields = ("path", "actor__email", "ip")

