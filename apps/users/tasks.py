from celery import shared_task


@shared_task
def task_send_password_reset_email(user_email):
    from apps.users.emails import PasswordResetEmail
    from apps.users.models import User
    from apps.users.utils import send_user_password_email

    try:
        user = User.objects.get(email=user_email)
        send_user_password_email(user, PasswordResetEmail)
    except User.DoesNotExist:
        pass
