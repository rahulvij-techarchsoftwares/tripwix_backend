from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.user.username}'s profile"


class WebsiteUser(User):
    """
    Proxy model for website users (non-staff users)
    """

    class Meta:
        proxy = True
        verbose_name = 'Website User'
        verbose_name_plural = 'Website Users'

    class Menu:
        icon = 'fa-users'


class ResetPasswordToken(models.Model):
    token = models.CharField(primary_key=True, max_length=120, unique=True)
