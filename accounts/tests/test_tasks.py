from django.core import mail

from accounts.models import VerificationCode
from accounts.tasks import delete_verification_code, send_verification_email


def test_send_verification_email():
    send_verification_email("test_email", "test_code")
    assert len(mail.outbox) == 1


def test_delete_verification_code(test_verification_code):
    delete_verification_code(test_verification_code.id)
    assert not VerificationCode.objects.filter(id=test_verification_code.id).exists()
