from django.urls import path

from accounts.views import CreateCustomUserAPIView, SendVerificationCodeAPIView

urlpatterns = [
    path("send_verification_code/", SendVerificationCodeAPIView.as_view(), name="send_verification_code"),
    path("create_account/", CreateCustomUserAPIView.as_view(), name="create_account"),
]
