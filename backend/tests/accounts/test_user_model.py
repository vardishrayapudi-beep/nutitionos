import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

pytestmark = pytest.mark.django_db


def test_create_user_uses_uuid_primary_key(user):
    assert isinstance(user.pk, uuid.UUID)


def test_create_user_sets_timestamps(user):
    assert user.created_at is not None
    assert user.updated_at >= user.created_at


def test_email_is_normalised_to_lowercase_and_trimmed(django_user_model):
    created = django_user_model.objects.create_user(email="  Dr.Mixed@EXAMPLE.com ", password="x" * 12)
    assert created.email == "dr.mixed@example.com"


def test_password_is_hashed_not_stored_in_plain_text(user, user_password):
    assert user.password != user_password
    assert user_password not in user.password
    assert user.check_password(user_password)


def test_user_without_password_has_unusable_password(django_user_model):
    invited = django_user_model.objects.create_user(email="invited@example.com")
    assert not invited.has_usable_password()


def test_email_is_required(django_user_model):
    with pytest.raises(ValueError):
        django_user_model.objects.create_user(email="", password="x" * 12)


def test_new_user_defaults_are_least_privilege(user):
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False


def test_create_superuser_sets_flags(superuser):
    assert superuser.is_staff is True
    assert superuser.is_superuser is True


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_false_flags(django_user_model, flag):
    with pytest.raises(ValueError):
        django_user_model.objects.create_superuser(email="bad@example.com", password="x" * 12, **{flag: False})


def test_authenticate_is_case_insensitive_on_email(user, user_password):
    from django.contrib.auth import authenticate

    assert authenticate(email="DOCTOR@Example.COM", password=user_password) == user
    assert authenticate(email="doctor@example.com", password="wrong-password") is None


def test_inactive_user_cannot_authenticate(user, user_password):
    from django.contrib.auth import authenticate

    user.is_active = False
    user.save()
    assert authenticate(email=user.email, password=user_password) is None


def test_full_name_and_str(user):
    assert user.get_full_name() == "Asha Rao"
    assert str(user) == "doctor@example.com"


def test_duplicate_email_rejected_via_manager(user, django_user_model):
    with pytest.raises(IntegrityError), transaction.atomic():
        django_user_model.objects.create_user(email="DOCTOR@example.com", password="x" * 12)


def test_database_constraint_blocks_case_variant_emails_even_without_save(django_user_model):
    """bulk_create skips User.save(), so only the DB-level lower(email) index can stop this."""
    first = django_user_model(email="Dup@example.com")
    second = django_user_model(email="dup@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        django_user_model.objects.bulk_create([first, second])


def test_model_validation_reports_case_insensitive_duplicate(user, django_user_model):
    candidate = django_user_model(email="Doctor@Example.com", first_name="X", last_name="Y")
    with pytest.raises(ValidationError):
        candidate.full_clean(exclude=["password"])
