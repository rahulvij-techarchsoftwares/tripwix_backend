from django.conf import settings
from django.core.mail import EmailMultiAlternatives

EMAIL_SETTINGS = {
    "from_email": getattr(settings, "EMAIL", {}).get("from_email", "localhost@localhost.com"),
    "recipients": getattr(settings, "EMAIL", {}).get("recipients", []),
    "cc_recipients": getattr(settings, "EMAIL", {}).get("cc_recipients", []),
    "bcc_recipients": getattr(settings, "EMAIL", {}).get("bcc_recipients", []),
}


# SEND EMAILS
def send_email(
    subject="",
    text_content="",
    html_content=None,
    from_email=EMAIL_SETTINGS["from_email"],
    recipients=EMAIL_SETTINGS["recipients"],
    cc_recipients=EMAIL_SETTINGS["cc_recipients"],
    bcc_recipients=EMAIL_SETTINGS["bcc_recipients"],
    fail_silently=True,
):
    email = EmailMultiAlternatives(
        subject,
        text_content,
        from_email,
        recipients,
        cc=cc_recipients,
        bcc=bcc_recipients,
    )

    if html_content:
        email.attach_alternative(html_content, "text/html")

    return email.send(fail_silently=fail_silently)
