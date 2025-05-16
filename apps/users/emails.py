from django import forms

from apps.email import EmailDefinition, register


@register("Password Reset Email")
class PasswordResetEmail(EmailDefinition):
    html_template = "email/password_reset.html"
    text_template = "email/password_reset.txt"

    subject = forms.CharField(initial="{{ site.name }} - Password reset")
    title = forms.CharField(initial="You've request a password reset in {{ site.name }}")
    sub_title = forms.CharField(initial="You're one step away from accessing your account.")
    message = forms.CharField(initial="The {{ site.name }} team", widget=forms.Textarea)

    @classmethod
    def sample_context(cls, bank):
        return {
            "passwd_reset_url": "https://example.com/password-reset",
        }
