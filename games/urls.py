from django.urls import path

from games.views import MyGameHistoryView

urlpatterns = [
    path("history/me/", MyGameHistoryView.as_view(), name="history_me"),
]
