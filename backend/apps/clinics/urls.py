from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.memberships.views import InvitationViewSet, MemberViewSet

from .views import ClinicMeView

app_name = "clinics"

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = [
    path("me/", ClinicMeView.as_view(), name="me"),
    path("", include(router.urls)),
]
