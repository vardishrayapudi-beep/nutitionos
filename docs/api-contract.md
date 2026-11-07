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

## Implemented endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/health/` | none | `200 {"status":"ok","database":"up"}` or `503 {"status":"unavailable","database":"down"}` |
| GET | `/api/v1/schema/` , `/api/v1/docs/` | none | OpenAPI schema / Swagger UI (development only) |

## Planned (NOT implemented - do not call)
Auth, clinics, doctors, patients, nutrition, prescriptions, grocery, food logs, reporting - as
listed in the master prompt, section 10. Endpoints are exposed only after authorization rules,
serializers and cross-clinic tests exist.
