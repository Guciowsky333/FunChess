# Create your views here.
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from accounts.models import CustomUser
from games.filters import GameHistoryFilter, GameHistoryFilterBackend
from games.models import Game
from games.serializers import GameHistorySerializer


class BaseGameHistoryView(generics.ListAPIView):
    queryset = Game.objects.none()
    serializer_class = GameHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [GameHistoryFilterBackend]
    filterset_class = GameHistoryFilter


@extend_schema(
    summary="Games History",
    description="""
    Returns all request user's games, sorted by the previous one by default 

    Business rules:
    - Authentication required.
    """,
    responses={
        200: OpenApiResponse(description="All user's games"),
        401: OpenApiResponse(description="Unauthorized"),
    },
)
class MyGameHistoryView(BaseGameHistoryView):
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

    def get_target_user(self):
        return self.request.user


@extend_schema(
    summary="Games History of provided player",
    description="""
    Returns all games of a player with provided username in the url, sorted by the previous one by default 
    
    Business rules:
    - Authentication required.
    - User with provided username must exist.
    """,
    responses={
        200: OpenApiResponse(description="All games of the user with provided username"),
        401: OpenApiResponse(description="Unauthorized"),
        404: OpenApiResponse(description="User with provided username not found"),
    },
)
class PlayerGameHistoryView(BaseGameHistoryView):
    def get_queryset(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(CustomUser, username=username)
        games = (
            Game.objects.filter(
                Q(white_player=user) | Q(black_player=user),
                status=Game.Status.FINISHED,
            )
            .select_related("white_player", "black_player", "time_control")
            .order_by("-finished_at", "-id")
        )
        return games

    def get_target_user(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(CustomUser, username=username)
        return user
