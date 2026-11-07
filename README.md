# Nutrition OS

Clinic-based medical nutrition management and execution platform (B2B2C SaaS).
*"Nutrition OS" is a temporary name.*

Doctors prescribe nutrition plans; patients struggle to follow them. Nutrition OS turns a
doctor-approved prescription into weekly meal schedules, recipes, grocery lists and progress
tracking. **The platform never diagnoses or prescribes - the doctor stays clinically responsible.**

> **Status: Sprint 1, Day 3 complete** - backend foundation, multi-tenancy core, and the auth API
> (register a clinic, log in, refresh, log out, "who am I"). Clinic management, doctors and patients
> come next - see the roadmap.
> See [docs/development-roadmap.md](docs/development-roadmap.md).

> **Data safety:** use synthetic data only until a legal and technical assessment (including
> India's DPDP Act) has been completed. Nothing here claims regulatory compliance.

## Stack

Python 3.12 - Django 5.2 LTS - Django REST Framework - PostgreSQL 16+ - JWT (simplejwt) -
drf-spectacular. Redis/Celery and React/TypeScript are added in later sprints.

## Local setup (Windows PowerShell)

Prerequisites: Python 3.12 (`py --version`), Git, and PostgreSQL 16+ (installer from postgresql.org;
remember the password you set for the `postgres` user).

```powershell
# 1. Go to the backend folder of this repo
cd $HOME\Documents\nutitionos\backend

# 2. Virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1
#    If PowerShell blocks the script:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 4. Create the database (psql ships with PostgreSQL; enter your postgres password when asked)
psql -U postgres -c "CREATE USER nutrition_os WITH PASSWORD 'choose-a-password' CREATEDB;"
psql -U postgres -c "CREATE DATABASE nutrition_os OWNER nutrition_os;"
#    If 'psql' is not found, use: & "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres ...

# 5. Configuration
copy .env.example .env
#    Edit .env: set DB_PASSWORD to the password from step 4 and generate DJANGO_SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 6. Create tables, run tests, start the server
python manage.py migrate
python -m pytest          # expect: 152 passed
python manage.py createsuperuser
python manage.py runserver
```

Then open:
- http://localhost:8000/api/v1/health/ - should show `{"status":"ok","database":"up"}`
- http://localhost:8000/api/v1/docs/ - interactive API documentation (development only)
- http://localhost:8000/admin/ - platform-operator admin (not for clinics)

### Try the API
With the server running, open http://localhost:8000/api/v1/docs/ (Swagger UI):
1. Expand `POST /api/v1/auth/register-clinic/` -> **Try it out** -> fill the example body -> **Execute**.
2. Copy the `access` token from the response, click **Authorize** (top right), paste it, then call
   `GET /api/v1/auth/me/` to see your clinic and role.

macOS/Linux: replace the activate line with `source .venv/bin/activate` and `py` with `python3`.

## Repository layout

```
backend/            Django project (config/ settings, apps/ domain modules, tests/)
docs/               architecture, database schema, API contract, roadmap & progress log
frontend/           React app (added later)
```

## Documentation

- [Architecture & decision log](docs/architecture.md)
- [Database schema](docs/database-schema.md)
- [API contract](docs/api-contract.md)
- [Roadmap, progress record & known issues](docs/development-roadmap.md)
