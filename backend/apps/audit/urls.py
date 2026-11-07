from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet

app_name = "audit"
router = DefaultRouter()
router.register("events", AuditLogViewSet, basename="event")
urlpatterns = router.urls
