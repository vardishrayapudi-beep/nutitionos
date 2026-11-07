"""Root URL configuration. All API routes live under /api/v1/."""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Django admin is for platform operators only, never for clinics.
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/clinics/", include("apps.clinics.urls")),
    path("api/v1/doctors/", include("apps.doctors.urls")),
    path("api/v1/patients/", include("apps.patients.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
    path("api/v1/", include("apps.common.urls")),
]

if settings.API_DOCS_ENABLED:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
        path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    ]
