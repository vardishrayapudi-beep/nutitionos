# Development roadmap & progress record

## Sprint 1 - Backend foundation (proposed day plan)

Models come before endpoints: `register-clinic` needs Clinic + Membership to exist first.

- [x] **Day 1** - Project init, settings split, PostgreSQL, custom User, first migration, health check, secure API defaults, tests, docs
- [ ] **Day 2** - `Clinic` + `Membership` models (roles, status, constraints), tenant-scoping helpers, cross-clinic test harness
- [ ] **Day 3** - Auth endpoints: `register-clinic`, `token`, `token/refresh`, `me`
- [ ] **Day 4** - Clinic endpoints: `clinics/me` (GET/PATCH), `clinics/members`, `clinics/invitations`
- [ ] **Day 5** - Doctor profiles
- [ ] **Day 6** - Patients (clinic-scoped `patient_code`, consent status, assign-doctor)
- [ ] **Day 7** - Role permissions pass + audit-log foundation
- [ ] **Day 8-9** - Cross-clinic isolation suite across every endpoint, login hardening, API docs polish
- [ ] **Day 10** - Buffer and sprint review

**Sprint 1 done when:** a clinic admin can register, log in, invite a doctor and add a patient, and each
clinic can retrieve only its own records. Sprint 2 does not start before this is tested and stable.

Later sprints follow section 11 of the master prompt (nutrition DB, prescriptions, patient portal,
grocery engine, AI food tracking, reporting/commercialisation).

---

## Progress record - Session 1 (Sprint 1, Day 1)

**Completed**
1. Researched current versions; chose Django 5.2 LTS (see architecture decision #1).
2. Project skeleton, split settings, env-based configuration, PostgreSQL connection.
3. Custom `User` (email login, UUID pk, case-insensitive unique email) + admin.
4. First migration applied; table structure inspected directly in PostgreSQL.
5. `apps.common`: abstract base model, API error envelope, `/api/v1/health/`.
6. Secure-by-default DRF, JWT settings with rotation and blacklist, rate limits.
7. OpenAPI schema generation, 26 automated tests, documentation set.

**Files created:** everything under `backend/` (config/, apps/common, apps/accounts, tests/, pytest.ini,
requirements*.txt, .env.example, manage.py), `docs/*.md`, `README.md`, `.gitignore`.

**Commands executed (Linux sandbox, Python 3.12.3, PostgreSQL 16.15):**
`manage.py check`, `makemigrations`, `migrate`, `pytest`, `makemigrations --check`,
`spectacular --validate`, `check --deploy` (production settings), live `runserver` + curl smoke test.

**Results**
- `pytest`: 26 passed (user model, DB constraint, admin, health, secure defaults, error format).
- `makemigrations --check`: no changes. `spectacular --validate`: schema generated.
- `check --deploy`: one warning, `security.W021` (HSTS preload) - **intentional**: preload is hard to undo; revisit at launch.
- Production settings refuse to start with empty `DJANGO_SECRET_KEY`, empty `DB_PASSWORD` or missing `DJANGO_ALLOWED_HOSTS`.
- Live server: health 200, docs 200, schema 200, admin 302 to login.

**NOT verified**
- Nothing has been run on the founder's Windows machine; the Windows setup steps in the README are
  written but untested by me.
- No production deployment, HTTPS, Redis, or load testing.

**Next tasks:** Sprint 1, Day 2 (Clinic + Membership + tenant scoping).

## Known issues / technical debt
1. Unknown `/api/...` URLs return Django's default 404 page (HTML), not the standard JSON error envelope.
2. Throttle counters use the default per-process cache; production needs a shared cache (Redis) for limits to be reliable.
3. `SECURE_PROXY_SSL_HEADER` assumes a trusted reverse proxy; confirm when the hosting target is chosen.
4. Swagger UI loads its assets from a CDN; fine for development, vendor them if docs are ever enabled in production.
5. Django 6.2 LTS (April 2027) upgrade should be planned.
