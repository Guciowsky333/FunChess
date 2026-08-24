import pytest
from django.core.exceptions import ValidationError

from games.validators import validate_chess_square


def test_validate_chess_square_valid():
    """
    It should not raise ValidationError because "e4" is valid chess square.
    """
    validate_chess_square("e4")


@pytest.mark.parametrize(
    "invalid_chess_square",
    [
        # value must contain 2 characters
        pytest.param("e", id="Too short"),
        pytest.param("e", id="Too Long"),
        # Allowed columns "abcdefgh"
        pytest.param("x5", id="Invalid column"),
        # Allowed rows "12345678"
        pytest.param("a9", id="Invalid row"),
        pytest.param("x9", id="Invalid both"),
    ],
)
def test_validate_chess_square_invalid(invalid_chess_square):
    with pytest.raises(ValidationError, match=invalid_chess_square):
        validate_chess_square(invalid_chess_square)
