from django.contrib import admin

from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "clinic", "role", "status", "created_at")
    list_filter = ("role", "status")
    search_fields = ("user__email", "clinic__name")
    list_select_related = ("user", "clinic")
    readonly_fields = ("id", "created_at", "updated_at")
