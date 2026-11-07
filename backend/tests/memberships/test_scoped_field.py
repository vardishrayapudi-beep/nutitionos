import uuid

import pytest
from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.memberships.fields import ClinicScopedPrimaryKeyRelatedField
from apps.memberships.models import Membership

pytestmark = pytest.mark.django_db
factory = APIRequestFactory()


class TargetSerializer(serializers.Serializer):
    target = ClinicScopedPrimaryKeyRelatedField(queryset=Membership.objects.all())


def request_for(user):
    request = Request(factory.get("/"))
    request.user = user
    return request


def test_accepts_object_from_the_callers_own_clinic(admin_a, doctor_a, clinic_a):
    own = Membership.objects.get(user=doctor_a, clinic=clinic_a)
    serializer = TargetSerializer(data={"target": str(own.id)}, context={"request": request_for(admin_a)})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["target"] == own


def test_rejects_object_from_another_clinic_like_a_nonexistent_one(admin_a, admin_b, clinic_b):
    foreign = Membership.objects.get(user=admin_b, clinic=clinic_b)
    context = {"request": request_for(admin_a)}

    foreign_result = TargetSerializer(data={"target": str(foreign.id)}, context=context)
    missing_result = TargetSerializer(data={"target": str(uuid.uuid4())}, context=context)

    assert not foreign_result.is_valid()
    assert not missing_result.is_valid()
    # Identical error: the caller learns nothing about other tenants' ids. (The message only
    # echoes back the id the caller themselves submitted, so mask that before comparing.)
    foreign_error = foreign_result.errors["target"][0]
    missing_error = missing_result.errors["target"][0]
    assert foreign_error.code == missing_error.code == "does_not_exist"
    assert str(foreign_error).replace(str(foreign.id), "<ID>") == \
        str(missing_error).replace(missing_result.data["target"], "<ID>")


def test_requires_request_in_context(admin_a, clinic_a):
    own = Membership.objects.get(user=admin_a, clinic=clinic_a)
    serializer = TargetSerializer(data={"target": str(own.id)})
    with pytest.raises(ImproperlyConfigured):
        serializer.is_valid()
