# Create your views here.
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from accounts.models import CustomUser
from games.filters import GameHistoryFilter, GameHistoryFilterBackend
from games.models import Game
from games.serializers import GameHistorySerializer


class GameHistoryPagination(PageNumberPagination):
    page_size = 10


class BaseGameHistoryView(generics.ListAPIView):
    queryset = Game.objects.none()
    serializer_class = GameHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [GameHistoryFilterBackend]
    filterset_class = GameHistoryFilter
    pagination_class = GameHistoryPagination

    def apply_ordering(self, queryset):
        """
        User can sort games starting from the older one to do that
        he has to provide "?order=finished_at" to url then games will be shown starting from the older one.
        If user doesn't provide "?order=finished_at" then games will be shown starting from the newest one by default.
        """
        order = self.request.query_params.get("order", None)

        # If user doesn't provide ordering the games are shown from the newest one by default
        if order is None:
            return queryset
        if order.lower() != "finished_at":
            raise ValidationError("Invalid order allowed 'finished_at'")
        # Returns games starting from the older one
        return queryset.order_by("finished_at", "id")


@extend_schema(
    summary="Games History",
    description="""
    Returns all request user's games, sorted by the previous one by default (Request user can also
    sorted games starting from the older one by providing ?order=finished_at in url). Request also can provided filters in url.
     

    Business rules:
    - Authentication required.
    - Allowed filters: ?result=win/lose/draw, ?color=white/black, ?category=bullet/blitz/rapid/
    - Allowed order: ?order=finished_at 
    """,
    parameters=[OpenApiParameter(name="order", required=False, type=str)],
    responses={
        200: OpenApiResponse(description="All user's games"),
        401: OpenApiResponse(description="Unauthorized"),
        400: OpenApiResponse(description="User provided invalid filters or order"),
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
        return self.apply_ordering(games)

    def get_target_user(self):
        return self.request.user


@extend_schema(
    summary="Games History of provided player",
    description="""
    Returns all games of a player with provided username in the url, sorted by the previous one by default (Request user can also
    sorted games starting from the older one by providing ?order=finished_at in url). Request also can provided filters in url.
    
    Business rules:
    - Authentication required.
    - User with provided username must exist.
    - Allowed filters: ?result=win/lose/draw, ?color=white/black, ?category=bullet/blitz/rapid/
    - Allowed order: ?order=finished_at 
    """,
    parameters=[OpenApiParameter(name="order", required=False, type=str)],
    responses={
        200: OpenApiResponse(description="All games of the user with provided username"),
        401: OpenApiResponse(description="Unauthorized"),
        404: OpenApiResponse(description="User with provided username not found"),
        400: OpenApiResponse(description="User provided invalid filters or order"),
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
        return self.apply_ordering(games)

    def get_target_user(self):
        username = self.kwargs.get("username")
        user = get_object_or_404(CustomUser, username=username)
        return user
