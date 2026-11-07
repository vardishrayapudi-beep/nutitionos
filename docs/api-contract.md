# API contract

Base path: `/api/v1/`. JSON only. Interactive docs at `/api/v1/docs/` (development only).

## Conventions
- **Auth:** `Authorization: Bearer <access token>`. Every endpoint requires auth unless stated.
- **Pagination:** page-number, 20 per page (`?page=2`).
- **Rate limits:** anonymous 60/min, authenticated 300/min, plus stricter per-client limits on credential endpoints (below). Exceeding a limit returns `429 throttled` with a `Retry-After` header. Counters are per-process until Redis is added.
- **Errors** always use this shape:

```json
{"error": {"code": "validation_error", "message": "The submitted data is invalid.",
           "details": {"email": ["This field is required."]}}}
```
`code` is machine-readable (`validation_error`, `not_authenticated`, `permission_denied`,
`not_found`, `throttled`, ...); `details` is `null` except for validation errors.

## Choosing a clinic (multi-tenancy)
Clinic-scoped endpoints act for the caller's **active clinic**, determined server-side from their
active membership. The client never sends a clinic in request bodies or query strings (any such
value is ignored).

- Member of exactly one clinic: nothing to send.
- Member of several clinics: send `X-Clinic-Id: <clinic uuid>` on every request. Without it the API
  answers `400 clinic_selection_required`.
- The header is validated; naming a clinic you do not actively belong to gives `403 clinic_access_denied`
  (identical whether that clinic exists or not).
- Accessing another clinic's object by id returns `404 not_found`.

| Status | `error.code` | Meaning |
|---|---|---|
| 401 | `not_authenticated` | missing/invalid/expired access token, or user deactivated |
| 403 | `no_active_membership` | user has no active membership in an active clinic (never joined, invited-only, suspended, or clinic deactivated) |
| 403 | `clinic_access_denied` | `X-Clinic-Id` names a clinic the user cannot use |
| 403 | `permission_denied` | role in the active clinic is not allowed to do this |
| 400 | `clinic_selection_required` | several clinics, no `X-Clinic-Id` |
| 400 | `invalid_clinic_header` | `X-Clinic-Id` is not a valid uuid |

## Implemented endpoints

| Method | Path | Auth | Rate limit | Description |
|---|---|---|---|---|
| GET | `/api/v1/health/` | none | none | `200 {"status":"ok","database":"up"}` or `503 {"status":"unavailable","database":"down"}` |
| POST | `/api/v1/auth/register-clinic/` | none | 5/hour | Create a clinic + its first admin (all-or-nothing) and log them in |
| POST | `/api/v1/auth/token/` | none | 10/min | Log in with email + password |
| POST | `/api/v1/auth/token/refresh/` | none | 30/min | Rotate a refresh token for a new pair |
| POST | `/api/v1/auth/logout/` | none | 30/min | Revoke a refresh token |
| GET | `/api/v1/auth/me/` | Bearer | default | Current user + clinic memberships |
| GET | `/api/v1/schema/` , `/api/v1/docs/` | none | default | OpenAPI schema / Swagger UI (development only) |

Limits on the credential endpoints are **per client address**. `X-Forwarded-For` is never trusted
unless the server is configured with the number of trusted proxies (`NUM_PROXIES`).

### `POST /auth/register-clinic/`
```json
{
  "clinic": {"name": "Sunrise Nutrition Clinic", "email": "hello@sunrise.example.com", "phone": "+91 98765 43210"},
  "admin":  {"email": "priya@sunrise.example.com", "password": "Correct-Horse-Battery-9",
             "first_name": "Priya", "last_name": "Sharma"}
}
```
`phone` is optional. Any other keys (e.g. `is_staff`, `role`, `slug`) are ignored. Password must pass
the server's policy (min 10 chars, not common, not all-numeric, not similar to name/email).

`201`:
```json
{
  "user":       {"id": "<uuid>", "email": "priya@sunrise.example.com", "first_name": "Priya", "last_name": "Sharma"},
  "clinic":     {"id": "<uuid>", "name": "Sunrise Nutrition Clinic", "slug": "sunrise-nutrition-clinic",
                 "email": "hello@sunrise.example.com", "phone": "+91 98765 43210",
                 "branding_mode": "platform", "is_active": true},
  "membership": {"id": "<uuid>", "role": "clinic_admin", "status": "active"},
  "tokens":     {"access": "<jwt, 15 min>", "refresh": "<jwt, 7 days>"}
}
```
Errors: `400 validation_error` (details nested as `{"admin": {"email": [...]}}`, e.g. email already
registered, weak password), `429 throttled`, `503 service_busy` (rare; safe to retry).

### `POST /auth/token/`
Body `{"email": "...", "password": "..."}` -> `200 {"access": "...", "refresh": "..."}`.
Email is case-insensitive. Wrong password and unknown email give the **same** `401 no_active_account`
response (no account enumeration). Access tokens contain only `user_id` plus standard claims.

### `POST /auth/token/refresh/`
Body `{"refresh": "..."}` -> `200 {"access": "...", "refresh": "..."}`. The submitted refresh token is
retired: using it again returns `401 token_not_valid`. Deactivated users cannot refresh. Always store the
*new* refresh token.

### `POST /auth/logout/`
Body `{"refresh": "..."}` -> `204`. Idempotent: an already-revoked or invalid token also returns 204.
Missing `refresh` -> `400 validation_error`. The short-lived access token remains valid until it
expires (max 15 minutes); clinic access, however, is re-checked on every request.

### `GET /auth/me/`
```json
{
  "id": "<uuid>", "email": "priya@sunrise.example.com", "first_name": "Priya", "last_name": "Sharma",
  "memberships": [
    {"id": "<uuid>", "role": "clinic_admin", "status": "active",
     "clinic": {"id": "<uuid>", "name": "Sunrise Nutrition Clinic", "slug": "sunrise-nutrition-clinic",
                "branding_mode": "platform", "is_active": true}}
  ],
  "needs_clinic_selection": false
}
```
Works for users with no clinic (`memberships: []`) and never needs `X-Clinic-Id`. Lists the caller's own
memberships in every status so the UI can show invitations or suspensions. `needs_clinic_selection` is
`true` when more than one membership currently grants access; the frontend then asks the user to choose
and sends that clinic's `id` as `X-Clinic-Id` on clinic-scoped requests.

## Planned (NOT implemented - do not call)
Clinics, doctors, patients, nutrition, prescriptions, grocery, food logs, reporting - as
listed in the master prompt, section 10. Endpoints are exposed only after authorization rules,
serializers and cross-clinic tests exist.
