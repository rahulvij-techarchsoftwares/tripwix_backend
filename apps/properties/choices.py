from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _

DEFAULT = "D"
SALE_TYPE_RENTAL = "r"

SALE_TYPE_CHOICES = (
    (DEFAULT, _('Default')),
    (SALE_TYPE_RENTAL, _('Rental')),
)

PROPERTIES_SORT_ORDER_CHOICES = (
    ('ra', _('Random Order')),
    ('ma', _('Manual Order')),
    ('ne', _('Newest First')),
    ('oe', _('Oldest First')),
    ('na', _('Name (ascending)')),
    ('nd', _('Name (descending)')),
    ('pa', _('Price (ascending)')),
    ('pd', _('Price (descending)')),
)

RATE_TYPE_CHOICES = (('p', _('Percentage')), ('f', _('Fixed')))
FEE_TYPE_CHOICES = (('p', _('Percentage')), ('c', _('Currency Amount')))

SEASON_CHOICES = (
    ('Low', _('Low')),
    ('Mid', _('Mid')),
    ('High', _('High')),
    ('Peak', _('Peak')),
    ('Other', _('Other')),
    ('Close', _('Close')),
)

# Details Choices
DETAIL_TYPE_TEXT = 'text'
DETAIL_TYPE_TRANS_TEXT = 'trans_text'
DETAIL_TYPE_BOOL = 'boolean'
DETAIL_TYPE_OPTION = 'option'
DETAIL_TYPE_OPTIONS = 'options'
DETAIL_TYPE_DATE = 'date'
DETAIL_TYPE_TIME = 'time'
DETAIL_TYPE_NUMBER = 'number'
DETAIL_TYPE_INTEGER = 'integer'
DETAIL_TYPE_COLOR = 'color'
DETAIL_TYPE_DESCRIPTION = 'description'
DETAIL_TYPE_TRANS_DESCRIPTION = 'trans_description'
DETAIL_TYPE_INTEGER_OPTIONS = 'integer_options'
DETAIL_TYPE_RATING = 'rating'
DETAIL_TYPE_VIDEOS = "videos"
DETAIL_TYPE_IMAGE = "image"
DETAIL_TYPE_360_IMAGE = "360_image"
DETAIL_TYPE_INTEGER_SUM = 'integer_sum'
DETAIL_TYPE_NUMBER_WITH_VALUE_TYPE_SELECTOR = 'number_with_value_type_selector'
DETAIL_TYPE_COUNTRY_VAT_CHOICES = 'country_vat_choices'

DETAIL_TYPE_CHOICES = (
    (DETAIL_TYPE_TEXT, _('Text')),
    (DETAIL_TYPE_TRANS_TEXT, _('Translatable Text')),
    (DETAIL_TYPE_BOOL, _('Boolean')),
    (DETAIL_TYPE_OPTION, _('Option')),
    (DETAIL_TYPE_OPTIONS, _('Options')),
    (DETAIL_TYPE_DATE, _('Date')),
    (DETAIL_TYPE_TIME, _('Time')),
    (DETAIL_TYPE_NUMBER, _('Number')),
    (DETAIL_TYPE_INTEGER, _('Integer')),
    (DETAIL_TYPE_COLOR, _('Color')),
    (DETAIL_TYPE_DESCRIPTION, _('Description')),
    (DETAIL_TYPE_TRANS_DESCRIPTION, _('Translatable Description')),
    (DETAIL_TYPE_INTEGER_OPTIONS, _('Integer Options')),
    (DETAIL_TYPE_RATING, _('Rating')),
    (DETAIL_TYPE_VIDEOS, _('Videos')),
    (DETAIL_TYPE_IMAGE, _('Image')),
    (DETAIL_TYPE_360_IMAGE, _('Image 360')),
    (DETAIL_TYPE_INTEGER_SUM, _('Integer with Sum')),
    (DETAIL_TYPE_NUMBER_WITH_VALUE_TYPE_SELECTOR, _('Number with Value Type Selector')),
    (DETAIL_TYPE_COUNTRY_VAT_CHOICES, _('Country VAT Choices')),
)

OPTION_CAN_ADD_RELATED = '1'
OPTION_CAN_CHANGE_RELATED = '2'
OPTION_CAN_DELETE_RELATED = '3'

OPTION_CAN_RELATED_CHOICES = (
    (OPTION_CAN_ADD_RELATED, _('can add related')),
    (OPTION_CAN_CHANGE_RELATED, _('can change related')),
)

EMAIL = 'email'
WHATSAPP = 'whatsapp'
PHONE = 'phone'

CONTACT_METHOD_CHOICES = ((EMAIL, _('Email')), (PHONE, _('Phone')), (WHATSAPP, _('Whatsapp')))

PERSON = 'Person'
COMPANY = 'Company'

ACCOUNT_TYPE_CHOICES = ((PERSON, 'Person'), (COMPANY, 'Company'))

ACCOUNT_TYPE_CHOICES_LIST = [PERSON, COMPANY]

AMB_RELATIONS = 'amb_relations'
DIRECT = 'direct'
OTHER = 'other'

ONBOARDING_SOURCE_CHOICES = (
    (AMB_RELATIONS, _('Amb. Relations')),
    (DIRECT, _('Direct')),
    (OTHER, _('Other')),
)

EN_US = 'en_us'
EN_GB = 'en_gb'
PT_PT = 'pt_pt'
PT_BR = 'pt_br'
ES = 'es'
FR = 'fr'
IT = 'it'
TR = 'tr'
OTHER_LANGUAGE = 'other'

PREFERRED_LANGUAGE_CHOICES = (
    (EN_US, _('en-us')),
    (EN_GB, _('en-gb')),
    (PT_PT, _('pt-pt')),
    (PT_BR, _('pt-br')),
    (ES, _('es')),
    (FR, _('fr')),
    (IT, _('it')),
    (TR, _('tr')),
    (OTHER_LANGUAGE, _('Other')),
)


class SyncStatusChoices(TextChoices):
    SYNCED = 'synced', _('Synced')
    NOT_SYNCED = 'not_synced', _('Not Synced')
    SYNCING = 'syncing', _('Syncing')
    SYNC_FAILED = 'sync_failed', _('Sync Failed')
    SYNC_PENDING = 'sync_pending', _('Sync Pending')
