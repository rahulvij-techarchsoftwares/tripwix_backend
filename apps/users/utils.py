from uuid import uuid4

from django.conf import settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.email.utils import send
from apps.users.emails import PasswordResetEmail


def send_user_password_email(user, definition=PasswordResetEmail):
    secret_with_pk = f"{user.pk}:{uuid4()}"
    uid = urlsafe_base64_encode(force_bytes(secret_with_pk))
    url = settings.FRONTOFFICE_URL + f"/en/auth/reset-password?token={uid}"
    context = {"passwd_reset_url": url}

    send(definition, context, [user.email])
