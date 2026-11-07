from django.contrib import admin
from django.utils import timezone

from .models import Ingredient


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Platform operators curate the CENTRAL ingredient database here (clinic is empty)."""

    list_display = ("name", "clinic", "category", "calories_per_100", "source", "verification_status")
    list_filter = ("verification_status", "category", ("clinic", admin.EmptyFieldListFilter))
    search_fields = ("name", "source", "source_reference")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["mark_verified"]

    @admin.action(description="Mark selected ingredients as VERIFIED against their source")
    def mark_verified(self, request, queryset):
        queryset.update(verification_status=Ingredient.Verification.VERIFIED,
                        verified_at=timezone.now(), verified_by=request.user)
