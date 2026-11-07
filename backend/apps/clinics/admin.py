from django.contrib import admin

from .models import Clinic


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "email", "branding_mode", "is_active", "created_at")
    list_filter = ("is_active", "branding_mode")
    search_fields = ("name", "slug", "email")
    readonly_fields = ("id", "created_at", "updated_at")
