import factory.fuzzy
from django.utils import timezone

from apps.email.models import EmailDefinitionModel


class EmailFactory(factory.django.DjangoModelFactory):
    name = 'drop activation'

    module_path = '/drop/email'

    data = {}

    allow_send = True

    last_sent_email_ts = factory.LazyFunction(timezone.now)

    last_sent_email_to = "test@test.com"

    class Meta:
        model = EmailDefinitionModel
