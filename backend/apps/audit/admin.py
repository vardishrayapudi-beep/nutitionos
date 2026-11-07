from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only view for platform operators. The database itself also refuses changes."""

    list_display = ("created_at", "action", "clinic", "actor_type", "actor", "target_type", "target_id")
    list_filter = ("action", "actor_type")
    search_fields = ("action", "target_id", "request_id")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
