from django.urls import path

from matchmaking.views import CheckTemporaryBanAPIView

urlpatterns = [
    path("check_if_banned/", CheckTemporaryBanAPIView.as_view(), name="check_if_banned"),
]
