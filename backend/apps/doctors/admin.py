from django.contrib import admin
from django.utils import timezone

from .models import DoctorProfile


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
    """Platform operators verify registration numbers here."""

    list_display = ("user", "specialization", "registration_number", "verification_status", "verified_at")
    list_filter = ("verification_status",)
    search_fields = ("user__email", "registration_number")
    readonly_fields = ("id", "created_at", "updated_at", "verified_at", "verified_by")
    actions = ["mark_verified", "mark_rejected"]

    @admin.action(description="Mark selected doctors as VERIFIED (registration number checked)")
    def mark_verified(self, request, queryset):
        queryset.update(verification_status=DoctorProfile.Verification.VERIFIED,
                        verified_at=timezone.now(), verified_by=request.user)

    @admin.action(description="Mark selected doctors as REJECTED")
    def mark_rejected(self, request, queryset):
        queryset.update(verification_status=DoctorProfile.Verification.REJECTED,
                        verified_at=None, verified_by=None)
