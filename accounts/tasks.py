from celery import shared_task
from django.core.mail import send_mail

from accounts.models import VerificationCode


@shared_task
def send_verification_email(email: str, code: int) -> None:
    send_mail(
        subject="Verification Email",
        message=f"Your verification code is {code}",
        from_email="FunChess@wp.com",
        recipient_list=[email],
    )


@shared_task
def delete_verification_code(verification_code_id: int) -> None:
    """
    Each VerificationCode is valid for 15 minutes so this task will be used to
    delete it after 15 minutes since it has been created.
    """
    VerificationCode.objects.filter(id=verification_code_id).delete()
