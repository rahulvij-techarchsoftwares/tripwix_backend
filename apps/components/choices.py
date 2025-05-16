from django.utils.translation import gettext_lazy as _

FIELD_TEXT = 'text'
FIELD_BOOL = 'boolean'
FIELD_OPTION = 'option'
FIELD_OPTIONS = 'options'
FIELD_DATE = 'date'
FIELD_TIME = 'time'
FIELD_DATETIME = 'datetime'
FIELD_NUMBER = 'number'
FIELD_INTEGER = 'integer'
FIELD_APP = 'app'
FIELD_CTA = 'cta'
FIELD_COLOR = 'color'
FIELD_DESCRIPTION = 'description'
FIELD_IMAGE = 'image'
FIELD_GALLERY = 'gallery'
FIELD_JSON_FIELD = 'json_field'
FIELD_EMAIL = 'email'
FIELD_PHONE = 'phone'
FIELD_FILE = 'file'

FIELD_CHOICES = (
    (FIELD_TEXT, _('text')),
    (FIELD_DESCRIPTION, _('description')),
    (FIELD_PHONE, _('phone number')),
    (FIELD_EMAIL, _('email')),
    (FIELD_COLOR, _('color')),
    (FIELD_OPTION, _('option')),
    (FIELD_DATE, _('date')),
    (FIELD_TIME, _('time')),
    (FIELD_DATETIME, _('datetime')),
    (FIELD_NUMBER, _('number')),
    (FIELD_BOOL, _('boolean')),
    (FIELD_INTEGER, _('integer')),
    (FIELD_APP, _('app')),
    (FIELD_CTA, _('cta')),
    (FIELD_JSON_FIELD, _('json field')),
    (FIELD_IMAGE, _('image')),
    (FIELD_FILE, _('file')),
)
