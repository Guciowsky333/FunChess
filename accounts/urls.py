from django.urls import path

from accounts.views import SendVerificationCodeAPIView

urlpatterns = [
    path("send_verification_code/", SendVerificationCodeAPIView.as_view(), name="send_verification_code"),
]
