from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedUUIDModel

# Slugs will later appear in white-label portal URLs, so names that could collide with
# our own routes or sound official are never handed out as-is.
RESERVED_SLUGS = frozenset(
    {"admin", "api", "app", "docs", "health", "login", "media", "static", "support", "www"}
)
SLUG_MAX_LENGTH = 60


def generate_unique_slug(name: str) -> str:
    """Build a URL-safe slug from a clinic name that no other clinic is using.

    Non-Latin names (e.g. Telugu or Hindi) slugify to an empty string, so we fall back to
    "clinic". Collisions get a numeric suffix: apollo-nutrition, apollo-nutrition-2, ...
    The database UNIQUE constraint remains the final guard against a race between two
    simultaneous registrations.
    """
    base = slugify(name)[:SLUG_MAX_LENGTH].strip("-") or "clinic"
    candidate, counter = base, 1
    while candidate in RESERVED_SLUGS or Clinic.objects.filter(slug=candidate).exists():
        counter += 1
        suffix = f"-{counter}"
        candidate = f"{base[: SLUG_MAX_LENGTH - len(suffix)]}{suffix}"
    return candidate


class Clinic(TimeStampedUUIDModel):
    """A tenant: one paying customer (clinic, hospital or independent practice).

    Every clinic-owned record in the system (patients, prescriptions, custom recipes, ...)
    will carry a foreign key to this table. A clinic must never see another clinic's data.
    """

    class BrandingMode(models.TextChoices):
        PLATFORM = "platform", "Nutrition OS branding"
        WHITE_LABEL = "white_label", "Clinic branding (white-label)"

    name = models.CharField(max_length=200)
    # Generated from `name` on first save and never changed afterwards, so links stay stable.
    slug = models.SlugField(max_length=SLUG_MAX_LENGTH, unique=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    branding_mode = models.CharField(
        max_length=20, choices=BrandingMode.choices, default=BrandingMode.PLATFORM
    )
    # Deactivating a clinic instantly cuts off every member (see memberships.tenancy).
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            # Enforced in the database too, so a bug or a raw query cannot store garbage.
            models.CheckConstraint(
                condition=models.Q(branding_mode__in=["platform", "white_label"]),
                name="clinics_clinic_branding_mode_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
