from django.core.exceptions import ValidationError


def validate_move(value):
    if len(value) != 2:
        raise ValidationError(f"{value} is not a valid chess square")

    column, row = [value[0], value[1]]
    if column not in "abcdefgh":
        raise ValidationError(f"{value} is not a valid chess square")

    if row not in "12345678":
        raise ValidationError(f"{value} is not a valid chess square")
