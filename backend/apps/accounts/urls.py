from django.urls import path

from .views import LoginView, LogoutView, MeView, RegisterClinicView, TokenRefreshRotatingView

app_name = "accounts"

urlpatterns = [
    path("register-clinic/", RegisterClinicView.as_view(), name="register-clinic"),
    path("token/", LoginView.as_view(), name="token"),
    path("token/refresh/", TokenRefreshRotatingView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
