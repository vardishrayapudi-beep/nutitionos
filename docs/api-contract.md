# API contract

Base path: `/api/v1/`. JSON only. Interactive docs at `/api/v1/docs/` (development only).

## Conventions
- **Auth:** `Authorization: Bearer <access token>`. Every endpoint requires auth unless stated.
- **Pagination:** page-number, 20 per page (`?page=2`).
- **Rate limits:** anonymous 60/min, authenticated 300/min (per-process until Redis is added).
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

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/health/` | none | `200 {"status":"ok","database":"up"}` or `503 {"status":"unavailable","database":"down"}` |
| GET | `/api/v1/schema/` , `/api/v1/docs/` | none | OpenAPI schema / Swagger UI (development only) |

## Planned (NOT implemented - do not call)
Auth, clinics, doctors, patients, nutrition, prescriptions, grocery, food logs, reporting - as
listed in the master prompt, section 10. Endpoints are exposed only after authorization rules,
serializers and cross-clinic tests exist.
