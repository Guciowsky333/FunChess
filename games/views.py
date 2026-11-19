# Create your views here.
from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.models import CustomUser
from games.models import Game
from games.serializers import GameHistorySerializer


class BaseGameHistoryView(generics.ListAPIView):
    serializer_class = GameHistorySerializer
    permission_classes = [IsAuthenticated]


@extend_schema(
    summary="Games History",
    description="""
    Returns all request user's games, sorted by the previous one by default 

    Business rules:
    - Authentication required.
    """,
    responses={
        200: OpenApiResponse(description="All user's games our player with provided username"),
        401: OpenApiResponse(description="Unauthorized"),
    },
)
class MyGameHistoryView(BaseGameHistoryView):
    serializer_class = GameHistorySerializer

    def get_queryset(self):
        user = CustomUser.objects.get(id=self.request.user.id)
        games = (
            Game.objects.filter(
                Q(white_player=user) | Q(black_player=user),
                status=Game.Status.FINISHED,
            )
            .select_related("white_player", "black_player", "time_control")
            .order_by("-finished_at", "-id")
        )
        return games
