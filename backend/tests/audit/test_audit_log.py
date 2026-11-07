import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.audit import service as audit
from apps.audit.models import AuditLog
from apps.memberships.tenancy import get_request_membership

pytestmark = pytest.mark.django_db
factory = APIRequestFactory()


def test_record_stores_event_with_target_and_metadata(admin_a, clinic_a):
    event = audit.record(action="member.role_changed", actor=admin_a, clinic=clinic_a,
                         target=clinic_a, old_role="staff", new_role="doctor")
    event.refresh_from_db()
    assert (event.action, event.target_type, event.target_id) == ("member.role_changed", "Clinic", str(clinic_a.id))
    assert event.metadata == {"old_role": "staff", "new_role": "doctor"}
    assert event.actor_type == "user"


def test_record_fills_actor_clinic_and_ip_from_the_request(admin_a, clinic_a):
    request = Request(factory.get("/", REMOTE_ADDR="203.0.113.9"))
    request.user = admin_a
    get_request_membership(request)  # resolves + caches the clinic, exactly as a real view would
    event = audit.record(action="thing.happened", request=request)
    assert event.actor == admin_a
    assert event.clinic == clinic_a
    assert event.ip_address == "203.0.113.9"


def test_system_events_have_no_actor():
    event = audit.record(action="system.cleanup")
    assert event.actor is None and event.actor_type == "system"


@pytest.mark.parametrize("key", ["email", "password", "first_name", "phone", "date_of_birth", "token", "note"])
def test_sensitive_keys_in_metadata_are_refused(key):
    with pytest.raises(ValueError):
        audit.record(action="x", **{key: "anything"})
    assert AuditLog.objects.count() == 0


def test_rows_cannot_be_updated_even_with_a_raw_query():
    event = audit.record(action="original")
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditLog.objects.filter(pk=event.pk).update(action="tampered")
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("UPDATE audit_auditlog SET action = 'tampered' WHERE id = %s", [event.pk])
    event.refresh_from_db()
    assert event.action == "original"


def test_rows_cannot_be_deleted():
    event = audit.record(action="keep-me")
    with pytest.raises(IntegrityError), transaction.atomic():
        event.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        AuditLog.objects.all().delete()
    assert AuditLog.objects.filter(pk=event.pk).exists()


def test_clinic_with_audit_history_cannot_be_deleted(clinic_a):
    audit.record(action="x", clinic=clinic_a)
    with pytest.raises(ProtectedError):
        clinic_a.delete()
