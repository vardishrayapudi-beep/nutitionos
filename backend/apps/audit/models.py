import uuid

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Append-only record of sensitive operations (who did what, to what, when, from where).

    - Rows can never be updated or deleted: a PostgreSQL trigger (see migration 0002) rejects
      both, so even a buggy deploy or a compromised application account cannot rewrite history.
    - ``metadata`` must NOT contain patient names, contact details, tokens or other sensitive
      content - only ids and field names. ``apps.audit.service.record`` enforces this.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    clinic = models.ForeignKey(
        "clinics.Clinic", null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # "user", "patient" (portal), "system", "anonymous"
    actor_type = models.CharField(max_length=20, default="user")
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["clinic", "-created_at"], name="audit_clinic_time_idx")]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
