from django.urls import path

from games.views import MyGameHistoryView, PlayerGameHistoryView

urlpatterns = [
    path("history/me/", MyGameHistoryView.as_view(), name="history_me"),
    path("history/<str:username>/", PlayerGameHistoryView.as_view(), name="history_player"),
]
