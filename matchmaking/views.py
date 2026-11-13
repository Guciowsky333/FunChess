# Create your views here.
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from matchmaking.services import check_if_user_has_temporary_ban


class CheckTemporaryBanAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Checks if user is temporary banned",
        description="""
        Checks if request user is temporary banned.
        
        Business rules:
          - Request user must be authenticated.
          """,
        responses={
            200: OpenApiResponse(description="Account details"),
            401: OpenApiResponse(description="Not authorized user"),
            429: OpenApiResponse(description="Too many requests"),
        },
    )
    def get(self, request):
        message = check_if_user_has_temporary_ban(request.user)
        return Response(message)
