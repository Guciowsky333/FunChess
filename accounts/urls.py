from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import CreateCustomUserAPIView, SendVerificationCodeAPIView, ThrottledTokenObtainPairView

urlpatterns = [
    path("token/", ThrottledTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("send_verification_code/", SendVerificationCodeAPIView.as_view(), name="send_verification_code"),
    path("create_account/", CreateCustomUserAPIView.as_view(), name="create_account"),
]
