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

## Multi-tenancy (non-negotiable; implemented from Sprint 1, Day 2)
Shared tables, every clinic-owned row carries a `clinic` foreign key, strict application-level checks:

1. The active clinic is derived from the authenticated user's **active Membership** - never from a
   `clinic_id` sent by the client.
2. Every clinic-owned queryset is filtered by that clinic.
3. Related objects in write requests are validated to belong to the same clinic.
4. Cross-clinic access returns 404 (not 403) so existence is not leaked.
5. Automated cross-clinic tests accompany every clinic-owned endpoint.

UUIDs are identifiers, not security controls.

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

## Deliberately not done yet
Redis/Celery, CORS (needed when React arrives), Docker, object storage, audit log, email sending.
