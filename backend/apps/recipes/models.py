from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.common.models import TimeStampedUUIDModel
from apps.common.vocab import MEAL_CATEGORY_CHOICES, QUANTITY_UNITS


class Recipe(TimeStampedUUIDModel):
    """A dish. Ingredient quantities are for ``servings`` servings.

    Visibility:
      central           clinic NULL    platform-owned master recipe, read-only for clinics
      clinic            clinic set     private to one clinic
      patient_specific  clinic+patient a variation made for one patient

    A clinic never edits a master recipe: it makes a COPY (see the customize endpoint), and the
    copy remembers where it came from in ``base_recipe``.
    """

    class Visibility(models.TextChoices):
        CENTRAL = "central", "Central (platform)"
        CLINIC = "clinic", "Clinic"
        PATIENT_SPECIFIC = "patient_specific", "Patient-specific"

    class Verification(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"

    clinic = models.ForeignKey("clinics.Clinic", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="recipes")
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.CLINIC)
    patient = models.ForeignKey("patients.Patient", null=True, blank=True, on_delete=models.PROTECT,
                                related_name="custom_recipes")
    base_recipe = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="variations")

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    meal_category = models.CharField(max_length=20, choices=MEAL_CATEGORY_CHOICES, default="any")
    servings = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    serving_size_description = models.CharField(max_length=100, blank=True)  # e.g. "1 bowl (about 250 g)"
    preparation_instructions = models.TextField(blank=True)
    preparation_time_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    dietary_tags = ArrayField(models.CharField(max_length=30), default=list, blank=True)

    data_source = models.CharField(max_length=200)
    source_reference = models.CharField(max_length=300, blank=True)
    verification_status = models.CharField(max_length=12, choices=Verification.choices,
                                           default=Verification.UNVERIFIED)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(servings__gt=0), name="recipes_servings_positive"),
            models.CheckConstraint(
                condition=(models.Q(visibility="central", clinic__isnull=True, patient__isnull=True)
                           | models.Q(visibility="clinic", clinic__isnull=False, patient__isnull=True)
                           | models.Q(visibility="patient_specific", clinic__isnull=False, patient__isnull=False)),
                name="recipes_visibility_consistent"),
            models.CheckConstraint(condition=models.Q(verification_status__in=["unverified", "verified"]),
                                   name="recipes_verification_valid"),
            models.CheckConstraint(condition=~models.Q(verification_status="verified") | models.Q(verified_at__isnull=False),
                                   name="recipes_verified_has_timestamp"),
        ]
        indexes = [models.Index(fields=["clinic", "meal_category"], name="recipes_clinic_meal_idx"),
                   models.Index(fields=["visibility"], name="recipes_visibility_idx")]

    @property
    def is_central(self) -> bool:
        return self.clinic_id is None

    def __str__(self):
        return self.name


class RecipeIngredient(TimeStampedUUIDModel):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name="lines")
    ingredient = models.ForeignKey("ingredients.Ingredient", on_delete=models.PROTECT, related_name="recipe_lines")
    quantity = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=5, choices=QUANTITY_UNITS)
    note = models.CharField(max_length=200, blank=True)  # e.g. "finely chopped"
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="recipe_lines_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit__in=["g", "ml", "piece"]), name="recipe_lines_unit_valid"),
        ]
