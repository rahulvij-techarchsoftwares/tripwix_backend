from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class CalendarStatusChoices(TextChoices):
    AVAILABLE = 'available', _('Available')
    BOOKED = 'booked', _('Booked')
    BLOCKED = 'blocked', _('Blocked')
    UNAVAILABLE = 'unavailable', _('Unavailable')


class ReservationStatusChoices(TextChoices):
    NO_STATUS = 'no_status', _('No Status')
    CONFIRMED = 'confirmed', _('Confirmed')
    ACCEPTED = 'accepted', _('Accepted')
    PENDING = 'pending', _('Pending')
    DENIED = 'denied', _('Denied')
    CANCELLED = 'cancelled', _('Cancelled')
    NO_SHOW = 'no_show', _('No Show')
    AWAITING_PAYMENT = 'awaiting_payment', _('Awaiting Payment')
    MOVED = 'moved', _('Moved')
    EXTENDED = 'extended', _('Extended')
    EDITED = 'edited', _('Edited')
    RETRACTED = 'retracted', _('Retracted')
    INQUIRY = 'inquiry', _('Inquiry')
    DECLINED_INQ = 'declined_inq', _('Declined Inquiry')
    PREAPPROVED = 'preapproved', _('Preapproved')
    OFFER = 'offer', _('Offer')
    WITHDRAWN = 'withdrawn', _('Withdrawn')
    EXPIRED = 'expired', _('Expired')
    TIMEDOUT = 'timedout', _('Timed Out')
    NOT_POSSIBLE = 'not_possible', _('Not Possible')
    NEW = 'new', _('New')
    DELETED = 'deleted', _('Deleted')


AVAILABLE_CALENDAR_RESERVATION_STATUS_MAPPING = (
    ReservationStatusChoices.DENIED,
    ReservationStatusChoices.CANCELLED,
    ReservationStatusChoices.DECLINED_INQ,
    ReservationStatusChoices.EXPIRED,
    ReservationStatusChoices.TIMEDOUT,
    ReservationStatusChoices.DELETED,
)

VALID_PROPERTY_TYPES = {
    "Apartment",
    "Bungalow",
    "Cabin",
    "Condominium",
    "Guesthouse",
    "House",
    "Guest suite",
    "Townhouse",
    "Vacation home",
    "Boutique hotel",
    "Nature lodge",
    "Hostel",
    "Chalet",
    "Dorm",
    "Villa",
    "Other",
    "Bed and breakfast",
    "Studio",
    "Hotel",
    "Resort",
    "Castle",
    "Aparthotel",
    "Boat",
    "Cottage",
    "Camping",
    "Serviced apartment",
    "Loft",
    "Hut",
}
