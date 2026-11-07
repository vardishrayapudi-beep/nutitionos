# Database schema

PostgreSQL 16+. All Nutrition OS tables use UUID primary keys plus `created_at` / `updated_at`
(via `apps.common.models.TimeStampedUUIDModel`). Money and nutrition values use `DecimalField`.

## Implemented

### `accounts_user`  (verified in PostgreSQL with `\d accounts_user`)

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| email | varchar(254) | UNIQUE, plus UNIQUE index on `lower(email)` (`accounts_user_email_ci_unique`) |
| password | varchar(128) | PBKDF2 hash; unusable password for invited users |
| first_name, last_name | varchar(150) | optional |
| is_active | boolean | default true |
| is_staff | boolean | may open Django admin (platform operators only) |
| is_superuser | boolean | via PermissionsMixin |
| last_login | timestamptz | |
| created_at, updated_at | timestamptz | |

Also created by Django/simplejwt: auth groups/permissions tables, `django_admin_log`, sessions,
`token_blacklist_*` (revoked/rotated refresh tokens).

### `clinics_clinic`  (verified in PostgreSQL)

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| name | varchar(200) | |
| slug | varchar(60) | UNIQUE; generated from name, never changes; reserved words skipped |
| email | varchar(254) | clinic contact email |
| phone | varchar(20) | optional, not yet format-validated |
| branding_mode | varchar(20) | `platform` \| `white_label`; CHECK constraint `clinics_clinic_branding_mode_valid` |
| is_active | boolean | false = every member is locked out immediately |
| created_at, updated_at | timestamptz | |

### `memberships_membership`  (verified in PostgreSQL)

| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| user_id | uuid FK -> accounts_user | `ON DELETE PROTECT` (application-level) |
| clinic_id | uuid FK -> clinics_clinic | `ON DELETE PROTECT` (application-level) |
| role | varchar(20) | `clinic_admin` \| `doctor` \| `staff`; CHECK `memberships_role_valid` |
| status | varchar(20) | `invited` (default) \| `active` \| `suspended`; CHECK `memberships_status_valid` |
| created_at, updated_at | timestamptz | |

Constraint `memberships_one_per_user_per_clinic`: UNIQUE (user_id, clinic_id).
Only `status = active` memberships in `is_active` clinics grant any access.

## Planned (not created yet - added when needed, per roadmap)
DoctorProfile, Patient (Sprint 1); Ingredient, Recipe, RecipeIngredient,
DietTemplate (Sprint 2); Prescription, MealSchedule (Sprint 3); Retailer, GroceryProduct,
ProductAvailability (Sprint 5); FoodLog, AIAnalysis (Sprint 6); ProgressReport (Sprint 7); AuditLog.

## Rules to enforce as tables arrive
- Patient code unique **per clinic** (`UNIQUE (clinic_id, patient_code)`).
- A doctor assigned to a patient must have an active membership in the same clinic.
- Approved prescriptions are immutable; revisions create a new version row.
- Foreign keys everywhere; no sensitive medical data in tokens, URLs or logs.
