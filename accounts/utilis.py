import secrets
import string


def generate_verification_code() -> str:
    """
    Returns a random verification code that including 6 random digits or characters
    """
    numbers_and_characters = string.digits + string.ascii_letters
    return "".join(secrets.choice(numbers_and_characters) for _ in range(6))
