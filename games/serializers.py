from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from accounts.models import CustomUser
from games.models import Game, TimeControl, UserRating


class UserRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRating
        fields = ["rating", "category"]


class TimeControlSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeControl
        fields = [
            "id",
            "category",
            "initial_time_seconds",
            "increment_seconds",
        ]


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
        ]


class GameHistorySerializer(serializers.ModelSerializer):
    time_control = TimeControlSerializer(read_only=True)
    white_player = SerializerMethodField()
    black_player = SerializerMethodField()

    class Meta:
        model = Game
        fields = [
            "id",
            "time_control",
            "result",
            "reason",
            "white_player",
            "black_player",
            "created_at",
            "finished_at",
        ]

    def get_white_player(self, obj):
        data = dict(PlayerSerializer(obj.white_player).data)
        # Adds white rating at the moment the game started
        data["rating"] = obj.white_rating
        # Adds white rating changed after the game
        data["change"] = obj.white_rating_change
        return data

    def get_black_player(self, obj):
        data = dict(PlayerSerializer(obj.black_player).data)
        # Adds black rating at the moment the game started
        data["rating"] = obj.black_rating
        # Adds black rating changed after the game
        data["change"] = obj.black_rating_change
        return data
