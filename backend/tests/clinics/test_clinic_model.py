import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.clinics.models import SLUG_MAX_LENGTH, Clinic

pytestmark = pytest.mark.django_db


def test_defaults(make_clinic):
    clinic = make_clinic("Defaults Clinic")
    assert isinstance(clinic.pk, uuid.UUID)
    assert clinic.is_active is True
    assert clinic.branding_mode == Clinic.BrandingMode.PLATFORM
    assert str(clinic) == "Defaults Clinic"


def test_slug_is_generated_from_name(make_clinic):
    assert make_clinic("Apollo Nutrition Clinic").slug == "apollo-nutrition-clinic"


def test_slug_collisions_get_numeric_suffixes(make_clinic):
    slugs = [make_clinic("Apollo").slug for _ in range(3)]
    assert slugs == ["apollo", "apollo-2", "apollo-3"]


def test_slug_is_stable_when_clinic_is_renamed(make_clinic):
    clinic = make_clinic("Old Name")
    clinic.name = "Completely New Name"
    clinic.save()
    clinic.refresh_from_db()
    assert clinic.slug == "old-name"


def test_reserved_slugs_are_never_handed_out(make_clinic):
    assert make_clinic("Admin").slug == "admin-2"
    assert make_clinic("API").slug == "api-2"


def test_non_latin_names_fall_back_to_a_generic_slug(make_clinic):
    assert make_clinic("క్లినిక్").slug == "clinic"
    assert make_clinic("क्लिनिक").slug == "clinic-2"


def test_slug_never_exceeds_max_length_even_with_suffix(make_clinic):
    first = make_clinic("a" * 200)
    second = make_clinic("a" * 200)
    assert len(first.slug) <= SLUG_MAX_LENGTH
    assert len(second.slug) <= SLUG_MAX_LENGTH
    assert second.slug.endswith("-2")


def test_database_rejects_duplicate_slugs_even_when_save_is_bypassed():
    with pytest.raises(IntegrityError), transaction.atomic():
        Clinic.objects.bulk_create([
            Clinic(name="One", slug="same", email="a@example.com"),
            Clinic(name="Two", slug="same", email="b@example.com"),
        ])


def test_database_rejects_invalid_branding_mode():
    with pytest.raises(IntegrityError), transaction.atomic():
        Clinic.objects.bulk_create([
            Clinic(name="Bad", slug="bad", email="a@example.com", branding_mode="rainbow"),
        ])
