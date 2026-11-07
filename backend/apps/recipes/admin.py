from django.contrib import admin
from django.utils import timezone

from .models import Recipe, RecipeIngredient


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 0
    autocomplete_fields = ["ingredient"]


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Platform operators curate CENTRAL recipes here (leave clinic empty, visibility=central)."""

    list_display = ("name", "visibility", "clinic", "meal_category", "data_source", "verification_status", "is_archived")
    list_filter = ("visibility", "verification_status", "meal_category", "is_archived")
    search_fields = ("name", "data_source")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [RecipeIngredientInline]
    actions = ["mark_verified"]

    @admin.action(description="Mark selected recipes as VERIFIED")
    def mark_verified(self, request, queryset):
        queryset.update(verification_status=Recipe.Verification.VERIFIED,
                        verified_at=timezone.now(), verified_by=request.user)
