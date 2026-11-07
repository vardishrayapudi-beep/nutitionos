# Architecture

## Style
**Modular monolith.** One Django project, one PostgreSQL database, domain logic split into apps under
`backend/apps/`. No microservices, Kubernetes or message brokers until a measured need exists.

```
HTTP request -> DRF view -> permission checks -> serializer (validation) -> app logic -> PostgreSQL
                                   |
                       secure-by-default: IsAuthenticated, throttling, JWT
```

Apps are created progressively as dependencies appear (see roadmap). Currently:

| App | Purpose |
|---|---|
| `apps.common` | Shared abstract model (`TimeStampedUUIDModel`), API error envelope, health check |
| `apps.accounts` | Custom `User` (email login). Holds no clinic/role data. |
| `apps.clinics` | `Clinic` - the tenant (one paying customer). |
| `apps.memberships` | `Membership` (user + clinic + role + status) and ALL tenant plumbing: resolver, permissions, queryset mixin, scoped related field. |

## Multi-tenancy (non-negotiable) - implemented in Sprint 1, Day 2
Shared tables; every clinic-owned row carries a `clinic` foreign key; strict application-level checks.

1. The active clinic is derived from the authenticated user's **active Membership in an active
   Clinic** (`apps/memberships/tenancy.py`) - never from a `clinic_id` sent by the client.
2. People who work at several clinics choose one with the **`X-Clinic-Id` header**. It is only a
   *selector*: it is validated against the user's own memberships on every request. A header naming
   a clinic the user does not belong to is refused - there is no silent fallback.
3. Every clinic-owned queryset is filtered by that clinic (`ClinicScopedQuerysetMixin`).
4. Related objects in write requests must belong to the same clinic
   (`ClinicScopedPrimaryKeyRelatedField`).
5. Cross-clinic access to an object returns **404** (not 403) so its existence is not revealed. A
   foreign and a nonexistent clinic id in the header produce byte-identical 403 responses.
6. Membership is checked on **every request**, so suspending a membership or deactivating a clinic
   takes effect immediately - even for JWTs that were already issued.
7. Automated cross-clinic tests accompany every clinic-owned endpoint (`tests/support/api.py ::
   assert_clinic_isolation`). The suite was mutation-tested: deliberately removing the clinic filter
   makes it fail.

UUIDs are identifiers, not security controls.

### Recipe: adding a clinic-owned endpoint
```python
# models.py  - the model gets a clinic foreign key
clinic = models.ForeignKey("clinics.Clinic", on_delete=models.PROTECT, related_name="patients")

# serializers.py  - clinic is read-only; relations to other clinic-owned models use the scoped field
class PrescriptionSerializer(serializers.ModelSerializer):
    patient = ClinicScopedPrimaryKeyRelatedField(queryset=Patient.objects.all())
    class Meta:
        model = Prescription
        fields = [...]
        read_only_fields = ["id", "clinic"]

# views.py  - mixin FIRST; add a role permission per action where needed
class PatientViewSet(ClinicScopedQuerysetMixin, viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [HasActiveClinicMembership()]
        return [IsClinicAdminOrDoctor()]

# tests  - one call proves isolation
assert_clinic_isolation(owner_client=..., intruder_client=..., list_url=..., detail_url=..., owned_id=...)
```

## Decision log

| # | Decision | Why |
|---|---|---|
| 1 | **Django 5.2 LTS**, not 6.1 | LTS supported to April 2028; healthcare product should not chase non-LTS releases. Plan to move to 6.2 LTS (due April 2027) deliberately. Django 6.1 also requires PostgreSQL 15+. |
| 2 | **PostgreSQL only**, no SQLite fallback | Dev must behave like production (UUID, functional unique indexes, later: row-level features). |
| 3 | **Custom User before first migration**, email as login, UUID pk | Swapping the user model after data exists is very painful. |
| 4 | **Case-insensitive email uniqueness enforced in the database** (`UNIQUE (lower(email))`) | Application-level normalisation alone can be bypassed (e.g. `bulk_create`). Tested. |
| 5 | **User has no role/clinic fields**; they live on Membership | One person can belong to several clinics; roles are per clinic. |
| 6 | **Secure-by-default DRF**: `IsAuthenticated` globally, rate limits, JSON only | A forgotten permission class must fail closed. Tested. |
| 7 | **JWT carries only `user_id`**; access 15 min, refresh 7 days, rotation + blacklist | Requirement: no sensitive data in tokens; revocable sessions. |
| 8 | **One error envelope** `{"error": {code, message, details}}` | Frontend handles all failures in one place; cheap now, costly to change later. |
| 9 | **Split settings** (`base`/`development`/`production`); production refuses to start without secrets | Misconfiguration should fail loudly. |
| 10 | **Explicit `DB_*` variables instead of `DATABASE_URL`** | Passwords with special characters need no URL-escaping. |
| 11 | **`requirements.txt` (runtime) + `requirements-dev.txt` (tests)**, exact pins | Reproducible installs; small deviation from the master prompt's single file. |
| 12 | Interactive API docs **off by default**, on in development | Do not advertise the API surface in production unless chosen. |
| 13 | **Membership is the only source of tenant access**; role and status live on it | One person, several clinics, a different role in each. |
| 14 | **`X-Clinic-Id` header = validated selector**, not a trusted value | Multi-clinic users need a way to choose; the server still decides. Single-clinic users need no header. |
| 15 | **Tenant access is checked per request, not stored in the JWT** | Instant revocation; tokens stay free of clinic/role/personal data (tested). |
| 16 | **Deactivate, never delete**: `PROTECT` on Membership -> User/Clinic | Preserves who-had-access-to-what history. Note: India DPDP erasure requests will need an anonymisation design before launch. |
| 17 | **Enum values enforced by database CHECK constraints** (role, status, branding mode) | Bad data cannot enter through raw queries or `bulk_create`. Tested. |
| 18 | Clinic **slug** auto-generated, immutable, reserved words skipped, unique in DB | Future white-label URLs must stay stable and must not collide with our routes. |
| 19 | Clinic **logo field deferred to Sprint 7** | Needs Pillow plus the private object storage decision; branding is a Sprint 7 feature. `branding_mode` exists now. |
| 20 | **Production rejects a `DJANGO_SECRET_KEY` shorter than 50 chars** | The key signs sessions and JWTs; a weak one is a silent vulnerability. Tested. |

## Deliberately not done yet
Redis/Celery, CORS (needed when React arrives), Docker, object storage, audit log, email sending, invitations flow, clinic logo.
