from django import template

from apps.core.utils import domain_with_proto

register = template.Library()


@register.simple_tag
def project_url_value():
    return domain_with_proto()
