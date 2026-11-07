from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .tenancy_views import MembershipTestViewSet

router = DefaultRouter()
router.register("memberships", MembershipTestViewSet, basename="test-membership")

urlpatterns = [path("test-api/", include(router.urls))]
