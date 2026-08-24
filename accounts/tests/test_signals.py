import pytest

from accounts.models import CustomUser
from games.models import UserRating


@pytest.mark.django_db
def test_create_ratings_for_new_user_signal():
    """
    In this test we create new user and check whether our signal correctly
    creates all ratings for this new user
    """
    new_user = CustomUser.objects.create_user(
        email="testuser1@test1.com", username="test_username", password="Test_password"
    )
    new_user_ratings = UserRating.objects.filter(user=new_user)

    bullet = new_user_ratings.get(category=UserRating.Category.BULLET)
    assert bullet.category == "bullet"
    assert bullet.rating == 300

    blitz = new_user_ratings.get(category=UserRating.Category.BLITZ)
    assert blitz.category == "blitz"
    assert blitz.rating == 300

    rapid = new_user_ratings.get(category=UserRating.Category.RAPID)
    assert rapid.category == "rapid"
    assert rapid.rating == 300
