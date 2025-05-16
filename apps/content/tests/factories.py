import factory
from django.utils import timezone

from apps.content.models import Content


class ContentFactory(factory.django.DjangoModelFactory):
    content_type = Content.Types.CONTENT

    unique_name = 'special-content'

    title = 'Some Special Content'

    content_text = 'lorem ipsum'

    class Meta:
        model = Content
