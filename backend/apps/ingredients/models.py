from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.functions import Lower

from apps.common.models import TimeStampedUUIDModel
from apps.common.vocab import INGREDIENT_CATEGORIES


class Ingredient(TimeStampedUUIDModel):
    """A food ingredient with nutrition values per 100 g (or per 100 ml for liquids).

    ``clinic`` NULL  -> CENTRAL ingredient: owned by the platform, read-only for clinics.
    ``clinic`` set   -> private to that clinic.
    Every row records where its numbers came from and whether anyone has verified them.
    """

    class Unit(models.TextChoices):
        GRAM = "g", "per 100 g"
        MILLILITRE = "ml", "per 100 ml"

    class Verification(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        VERIFIED = "verified", "Verified"
        DISPUTED = "disputed", "Disputed"

    clinic = models.ForeignKey("clinics.Clinic", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="ingredients")
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=INGREDIENT_CATEGORIES, default="other")
    standard_unit = models.CharField(max_length=2, choices=Unit.choices, default=Unit.GRAM)
    # Lets recipes say "2 pieces" for countable items (egg, banana). Only for gram-based items.
    grams_per_piece = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)

    calories_per_100 = models.DecimalField(max_digits=7, decimal_places=2)
    protein_g_per_100 = models.DecimalField(max_digits=6, decimal_places=2)
    carbs_g_per_100 = models.DecimalField(max_digits=6, decimal_places=2)
    fat_g_per_100 = models.DecimalField(max_digits=6, decimal_places=2)
    fibre_g_per_100 = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    allergens = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    dietary_flags = ArrayField(models.CharField(max_length=30), default=list, blank=True)

    source = models.CharField(max_length=200)  # e.g. "IFCT 2017", "Manufacturer label", "Clinic lab"
    source_reference = models.CharField(max_length=300, blank=True)  # table/code/url
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
            models.UniqueConstraint(Lower("name"), "clinic", name="ingredients_name_unique_per_clinic",
                                    condition=models.Q(clinic__isnull=False)),
            models.UniqueConstraint(Lower("name"), name="ingredients_central_name_unique",
                                    condition=models.Q(clinic__isnull=True)),
            models.CheckConstraint(condition=models.Q(calories_per_100__gte=0, calories_per_100__lte=900),
                                   name="ingredients_calories_plausible"),
            models.CheckConstraint(condition=models.Q(protein_g_per_100__gte=0, protein_g_per_100__lte=100,
                                                      carbs_g_per_100__gte=0, carbs_g_per_100__lte=100,
                                                      fat_g_per_100__gte=0, fat_g_per_100__lte=100,
                                                      fibre_g_per_100__gte=0, fibre_g_per_100__lte=100),
                                   name="ingredients_macros_plausible"),
            models.CheckConstraint(condition=models.Q(standard_unit__in=["g", "ml"]),
                                   name="ingredients_unit_valid"),
            models.CheckConstraint(condition=models.Q(verification_status__in=["unverified", "verified", "disputed"]),
                                   name="ingredients_verification_valid"),
            models.CheckConstraint(condition=~models.Q(verification_status="verified") | models.Q(verified_at__isnull=False),
                                   name="ingredients_verified_has_timestamp"),
            models.CheckConstraint(condition=models.Q(grams_per_piece__isnull=True) | models.Q(grams_per_piece__gt=0),
                                   name="ingredients_piece_weight_positive"),
        ]
        indexes = [models.Index(fields=["clinic", "category"], name="ingredients_clinic_cat_idx")]

    @property
    def is_central(self) -> bool:
        return self.clinic_id is None

    def __str__(self):
        return self.name
