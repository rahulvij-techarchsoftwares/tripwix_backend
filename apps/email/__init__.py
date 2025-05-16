from apps.email.decorators import register  # noqa: F401
from apps.email.options import AlreadyRegistered, EmailDefinition, definitions  # noqa: F401
from apps.email.utils import send  # noqa: F401

default_app_config = 'apps.email.apps.EmailAppConfig'
