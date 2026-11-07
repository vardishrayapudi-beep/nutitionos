import pytest


@pytest.fixture
def user_password():
    return "Str0ng-Test-Passw0rd!"


@pytest.fixture
def user(django_user_model, user_password):
    return django_user_model.objects.create_user(
        email="doctor@example.com",
        password=user_password,
        first_name="Asha",
        last_name="Rao",
    )


@pytest.fixture
def superuser(django_user_model, user_password):
    return django_user_model.objects.create_superuser(
        email="root@example.com",
        password=user_password,
        first_name="Platform",
        last_name="Operator",
    )
