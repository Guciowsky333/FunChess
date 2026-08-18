from accounts.models import VerificationCode
from accounts.tasks import delete_verification_code, send_verification_email


def create_verification_code(email: str):
    """
    Creates a VerificationCode model with specified email, generates code and sends this code to this email

    Important : This code will be valid only for 15 minutes after this time VerificationCode model
    with this code and email will be deleted.
    """

    verification_code = VerificationCode.objects.create(email=email)
    send_verification_email.delay(email, verification_code.code)
    delete_verification_code.apply_async(args=[verification_code.id], countdown=900)
