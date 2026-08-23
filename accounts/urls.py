from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ChangeAvatarAPIView,
    ChangePasswordAPIView,
    ChangeUsernameAPIView,
    CreateCustomUserAPIView,
    GoogleOAuth2View,
    LogoutAPIView,
    ResetPasswordAPIView,
    SendResetPasswordCodeAPIView,
    SendVerificationCodeAPIView,
    ThrottledTokenObtainPairView,
)

urlpatterns = [
    path("token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("send_verification_code/", SendVerificationCodeAPIView.as_view(), name="send_verification_code"),
    path("create_account/", CreateCustomUserAPIView.as_view(), name="create_account"),
    path("google-login/", GoogleOAuth2View.as_view(), name="google-login"),
    path("change_avatar/", ChangeAvatarAPIView.as_view(), name="change_avatar"),
    path("send_reset_password_code/", SendResetPasswordCodeAPIView.as_view(), name="send_reset_password_code"),
    path("reset_password/", ResetPasswordAPIView.as_view(), name="reset_password"),
    path("change_password/", ChangePasswordAPIView.as_view(), name="change_password"),
    path("change_username/", ChangeUsernameAPIView.as_view(), name="change_username"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]
