from django.conf import settings

from apps.core.email import send_email
from apps.core.utils import domain_with_proto


def send(email_definition, context, recipients, **options):
    from django.contrib.sites.models import Site

    # DEFAULT GLOBAL CONTEXT
    email_context = {
        'proto_and_domain': domain_with_proto(),
        'site': Site.objects.get_current(),
    }
    email_context.update(context)

    email = email_definition(context=email_context)

    # do not send emails during testing
    if getattr(settings, "TESTING", False):
        return

    if email.allow_send(recipients):
        send_email(
            **options,
            subject=email.get_subject(),
            text_content=email.get_text_content(),
            html_content=email.get_html_content(),
            recipients=recipients,
        )
