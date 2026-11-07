from rest_framework.routers import DefaultRouter

from .views import DoctorProfileViewSet

app_name = "doctors"
router = DefaultRouter()
router.register("", DoctorProfileViewSet, basename="doctor")
urlpatterns = router.urls
