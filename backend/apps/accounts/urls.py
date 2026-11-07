from django.urls import path

from .views import (
    AcceptInvitationView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterClinicView,
    ResendVerificationView,
    TokenRefreshRotatingView,
    VerifyEmailView,
)

app_name = "accounts"

urlpatterns = [
    path("register-clinic/", RegisterClinicView.as_view(), name="register-clinic"),
    path("token/", LoginView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshRotatingView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("invitations/accept/", AcceptInvitationView.as_view(), name="invitation-accept"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("verify-email/resend/", ResendVerificationView.as_view(), name="verify-email-resend"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
]
