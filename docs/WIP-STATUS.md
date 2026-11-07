# Work-in-progress status (branch `wip/sprint-1-completion`)

This branch is a **checkpoint of unfinished work**. `main` contains only code that was tested.

## Tested (247 automated tests passing when this checkpoint was taken)
- Sprint 1 Days 1-3: project foundation, custom User, Clinic, Membership, tenant isolation, auth API.
- Audit log (append-only, database trigger), email verification, password reset / change.
- Clinic settings (`/clinics/me/`), members, invitations (email-only tokens), last-admin rule.

## Written but NOT tested (tests were paused on request)
- Doctor profiles (`apps/doctors`) and `/api/v1/doctors/`
- Patients (`apps/patients`) incl. consent, doctor assignment, monitoring flag, `/api/v1/patients/`
- Audit events endpoint `/api/v1/audit/events/`
- Migrations for the three items above apply cleanly and `manage.py check` passes, nothing more.

## Started, not usable yet
- Sprint 2: `apps/ingredients` and `apps/recipes` models only (not registered in INSTALLED_APPS,
  no migrations, no API, no seed data).

## Not started
- Rest of Sprint 2 (diet templates, APIs, seed data), Sprints 3-7 (prescriptions, patient portal,
  grocery engine, AI food tracking, reporting, subscriptions/billing, deployment files).

Do not deploy this branch or use it with real patient data.
