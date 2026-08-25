from rest_framework import serializers

from games.models import UserRating


class UserRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRating
        fields = ["rating", "category"]
