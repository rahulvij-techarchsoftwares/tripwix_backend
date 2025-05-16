import logging

from django.conf import settings
from django.db import transaction

from apps.external_apis.pipedrive.sdk import PipedriveAPI
from apps.pipedrive.models import Deal, Organization, Person
from apps.properties.models import Property

logger = logging.getLogger(__name__)


def upsert_person(person_data: dict):
    with transaction.atomic():
        organization_id = person_data['org_id']['value'] if person_data.get('org_id') else None
        organization = None
        if organization_id:
            organization = Organization.objects.filter(pipedrive_id=organization_id).first()
        person = Person.objects.filter(pipedrive_id=person_data['id']).first()
        if person:
            person.name = person_data['name']
            person.email = person_data.get('email', [{}])[0].get('value', '')
            person.phone = person_data.get('phone', [{}])[0].get('value', '')
            person.pipedrive_metadata = person_data
            person.organization = organization
            person.save()
        else:
            Person.objects.create(
                pipedrive_id=person_data['id'],
                name=person_data['name'],
                email=person_data.get('email', [{}])[0].get('value', ''),
                phone=person_data.get('phone', [{}])[0].get('value', ''),
                pipedrive_metadata=person_data,
                organization=organization,
            )


def upsert_organization(organization_data: dict):
    with transaction.atomic():
        organization = Organization.objects.filter(pipedrive_id=organization_data['id']).first()
        name = organization_data.get('name') or ''
        address = organization_data.get('address') or ''
        if organization:
            organization.name = name
            organization.address = address
            organization.pipedrive_metadata = organization_data
            organization.save()
            return
        organization = Organization.objects.create(
            pipedrive_id=organization_data['id'],
            name=name,
            address=address,
            pipedrive_metadata=organization_data,
        )


def upsert_deal(deal_data: dict, organization_obj: Organization):
    with transaction.atomic():
        deal = Deal.objects.filter(pipedrive_id=deal_data['id']).first()
        if deal:
            deal.title = deal_data['title']
            deal.value = deal_data['value']
            deal.status = deal_data['status']
            deal.currency = deal_data['currency']
            deal.checkin_date = deal_data.get('checkin_date')
            deal.checkout_date = deal_data.get('checkout_date')
            deal.number_of_guests = deal_data.get('number_of_guests')
            deal.property_id = deal_data.get('property_id')
            deal.source_url = deal_data.get('source_url')
            deal.pipedrive_metadata = deal_data
            deal.save()
            return
        deal = Deal.objects.create(
            pipedrive_id=deal_data['id'],
            title=deal_data['title'],
            value=deal_data['value'],
            status=deal_data['status'],
            organization=organization_obj,
            currency=deal_data['currency'],
            checkin_date=deal_data.get('checkin_date'),
            checkout_date=deal_data.get('checkout_date'),
            number_of_guests=deal_data.get('number_of_guests'),
            property_id=deal_data.get('property_id'),
            source_url=deal_data.get('source_url'),
            pipedrive_metadata=deal_data,
        )


def sync_pipedrive_persons():
    pipedrive_api = PipedriveAPI()
    response = pipedrive_api.get_persons()
    if response.get('success', False):
        persons_data = response.get('data', [])
        for person_data in persons_data:
            upsert_person(person_data)
    else:
        logger.error(f'Failed to fetch data from Pipedrive API: {response}')


def sync_organization_data():
    pipedrive_api = PipedriveAPI()
    organizations = pipedrive_api.get_organizations()
    organization_data_list = organizations.get('data', [])
    for organization_data in organization_data_list:
        upsert_organization(organization_data)


def sync_deals_data(organization_id=None):
    pipedrive_api = PipedriveAPI()
    if not organization_id:
        queryset = Organization.objects.all()
    else:
        queryset = Organization.objects.filter(pipedrive_id=organization_id)
    for organization in queryset:
        deal_offset = organization.deal_offset
        has_more_deals = True
        while has_more_deals:
            response = pipedrive_api.get_organization_deals(
                organization_id=organization.pipedrive_id, offset=deal_offset
            )
            deals = response['data']
            if not deals:
                break
            if not response['additional_data']['pagination']['more_items_in_collection']:
                deal_offset = response['additional_data']['pagination']['start'] + len(deals) + 1
                has_more_deals = False
            else:
                deal_offset = (
                    response['additional_data']['pagination']['start']
                    + response['additional_data']['pagination']['limit']
                    + 1
                )
            for deal in deals:
                upsert_deal(deal, organization)
        organization.deal_offset = deal_offset
        organization.save()


def process_inquiry_create(inquiry_id):
    pipedrive_api = PipedriveAPI()

    try:
        from apps.leads.models import Inquiry

        inquiry = Inquiry.objects.get(id=inquiry_id)
    except Inquiry.DoesNotExist:
        logging.error(f"Inquiry with id {inquiry_id} does not exist.")
        return
    property_code = ''
    property_name = ''
    if inquiry.property_id:
        try:
            property = Property.objects.get(id=inquiry.property_id)
            property_code = property.reference
            property_name = property.title
        except Property.DoesNotExist:
            logging.error(f"Property with id {inquiry.property_id} does not exist.")

    person_data = {
        'name': f" {inquiry.first_name} {inquiry.last_name}".strip(),
        "email": inquiry.email,
        "phone": inquiry.phone_number,
        "0661669830067aa6bb4a0ef40ef29b0ad1e30ad8": "Yes" if inquiry.smsMarketing else "No",
    }

    try:
        person_response = pipedrive_api.create_person(person_data)
    except Exception as e:
        logging.error(f"Failed to create person in Pipedrive: {e}")
        return

    if person_response.get('success'):
        person_id = person_response['data']['id']
    else:
        logging.error(f"Failed to create person in Pipedrive: {person_response}")
        return

    field_mapping = {
        'destination': 'c82769629fd7c9a44400cc8cf55c9b013af22542',
        'country': 'fcafa9a2ca81043ab642561ada3d8ad5448397ef',
        'property_id': 'fa750267172c201eade5cfa01ec619c14b6b366c',
        'number_of_guests': '31fa555542deadcc0880c3d77817f3d39d305bf9',
        'checkin_date': '475fa5f967f2427cd99d6b4700c4fb892d1600f8',
        'checkout_date': '7f2705822f7a873b5c98625ae016ba36b51605aa',
        'requested_nights': 'e94614c60da086fea209408f23909c9f362b9bae',
        'flexible_dates': 'da1218730c67c6173edde3efd7c6294bcd91ba37',
        'property_name': 'aab58297198dcaac6ad4ac16383193da353c893c',
        'source_url': '9b4a9505a7ed17f363d178cd5176b946ca1c87ba',
        'budget': 'cdac6d76a3abcf1af57956bf3ad8f028aca25d3f',
        'property_type': '0241caf5f2bd6b292991ebcecebdf327ec355453',
        'bedrooms': '4e51ba56ea37768cc12dcdcfb5fdcad872f3f26a',
        'comments': '599f6bf954cb1dc990bdcb0fc9ca6a4b1c7aa6de',
    }

    custom_fields = {}

    custom_fields[field_mapping['checkin_date']] = (
        inquiry.checkin_date.strftime('%Y-%m-%d') if inquiry.checkin_date else None
    )
    custom_fields[field_mapping['checkout_date']] = (
        inquiry.checkout_date.strftime('%Y-%m-%d') if inquiry.checkout_date else None
    )
    custom_fields[field_mapping['number_of_guests']] = inquiry.number_of_guests
    custom_fields[field_mapping['flexible_dates']] = 'Yes' if inquiry.is_travel_date_flexible else 'No'
    custom_fields[field_mapping['source_url']] = inquiry.source_url
    custom_fields[field_mapping['budget']] = 'Unknown'

    if inquiry.checkin_date and inquiry.checkout_date:
        requested_nights = (inquiry.checkout_date - inquiry.checkin_date).days
        custom_fields[field_mapping['requested_nights']] = requested_nights
    else:
        custom_fields[field_mapping['requested_nights']] = None

    if inquiry.property_id:
        try:
            property = Property.objects.get(id=inquiry.property_id)
            custom_fields[field_mapping['property_id']] = property.reference
            custom_fields[field_mapping['property_name']] = property.name
            custom_fields[field_mapping['destination']] = property.location.name if property.location else ''
            custom_fields[field_mapping['country']] = (
                property.location.country.name if property.location and property.location.country else ''
            )
            custom_fields[field_mapping['property_type']] = 'Property'
        except Property.DoesNotExist:
            logging.error(f"Property with reference {inquiry.property_id} does not exist.")

    custom_fields[field_mapping['bedrooms']] = (
        inquiry.number_of_bedrooms if hasattr(inquiry, 'number_of_bedrooms') else 0
    )
    custom_fields[field_mapping['comments']] = str(inquiry.note) if inquiry.note else ""

    deal_data = {
        'title': f"{property_code}, {property_name} - {inquiry.first_name} {inquiry.last_name}".strip(),
        'person_id': person_id,
        'value': 0,
        'currency': 'USD',
        '6f6d46a3cca8fa33f77f705dd0ab00a8df17c9dd': 61,
    }

    deal_data.update(custom_fields)

    deal_response = pipedrive_api.create_deal(deal_data)

    if not deal_response.get('success'):
        logging.error(f"Failed to create deal in Pipedrive: {deal_response}")


def process_lead_create(lead_id):
    try:
        from apps.leads.models import Lead

        lead = Lead.objects.get(id=lead_id)
    except Lead.DoesNotExist:
        logging.error(f"Lead with ID {lead_id} does not exist.")
        return

    pipedrive_api = PipedriveAPI()

    preferred_destination_map = {
        "barbados": "Barbados",
        "bequia": "Bequia",
        "greek_islands": "Greek Islands",
        "mykonos": "Mykonos",
        "florence_area": "Florence Area",
        "positano_area": "Positano Area",
        "lake_como": "Lake Como",
        "sicily_sardinia": "Sicily and Sardinia",
        "tuscany_umbria": "Tuscany and Umbria",
        "careyes": "Careyes",
        "colima": "Colima",
        "los_cabos": "Los Cabos",
        "punta_mita": "Punta de Mita Area",
        "puerto_vallarta": "Puerto Vallarta",
        "riviera_maya": "Riviera Maya",
        "riviera_nayarit": "Riviera Nayarit",
        "sayulita_area": "Sayulita Area",
        "algarve": "Algarve",
        "douro_valley": "Douro Valley",
        "cascais_sintra_estoril": "Cascais Sintra Estoril",
        "lisbon_area": "Lisbon Area",
        "comporta_area": "Comporta Area",
        "alentejo": "Alentejo",
        "nazare_area": "Nazare Area",
        "northern_portugal": "Northern Portugal",
        "marbella_area": "Marbella Area",
        "ronda_area": "Ronda Area",
        "seville_area": "Seville Area",
        "istanbul": "Istanbul",
        "kalkan_kas": "Kalkan and Kas",
        "marmaris": "Marmaris",
        "gocek": "Göcek",
        "bodrum": "Bodrum",
    }
    desired_destination_value = lead.desired_destination or ""
    if isinstance(desired_destination_value, str):
        raw_list = [x.strip() for x in desired_destination_value.split(",") if x.strip()]
    else:
        raw_list = desired_destination_value if desired_destination_value else []

    final_dest_list = []
    for item in raw_list:
        mapped = preferred_destination_map.get(item.lower(), "Other")
        final_dest_list.append(mapped)

    desired_destination_value = lead.desired_destination or lead.how_can_we_help_extra_field
    if isinstance(desired_destination_value, str):
        desired_destination_value = [x.strip() for x in desired_destination_value.split(",") if x.strip()]
    how_can_we_help_value = lead.how_can_we_help or lead.how_can_we_help_extra_field
    if how_can_we_help_value == "villa_rental":
        how_can_we_help_value = "I'm interested in a villa rental"
    elif how_can_we_help_value == "property_management":
        how_can_we_help_value = "I would like to know more about property management"
    elif how_can_we_help_value == "homeowner_partner":
        how_can_we_help_value = "I am a homeowner and would like to partner with you"
    elif how_can_we_help_value == "travel_agent_inquiry":
        how_can_we_help_value = "I am a travel agent with an inquiry"
    elif how_can_we_help_value == "book_services":
        how_can_we_help_value = "Would like to book extra services and/or activities"
    elif how_can_we_help_value == "press_member_info":
        how_can_we_help_value = "I am a Press Member and desire information on the company"
    elif how_can_we_help_value == "other":
        how_can_we_help_value = "Other (specify the service)"

    where_heard_value = lead.where_heard_about_us or lead.where_heard_about_us_extra_field

    if where_heard_value == "traveled_before":
        where_heard_value = "I have traveled with you before"
    elif where_heard_value == "word_of_mouth":
        where_heard_value = "Word of mouth"
    elif where_heard_value == "referral":
        where_heard_value = "Referral"
    elif where_heard_value == "search_engine":
        where_heard_value = "Search (Google"
    elif where_heard_value == "online_advertising":
        where_heard_value = "Online Advertising"
    elif where_heard_value == "influencer":
        where_heard_value = "Influencer"
    elif where_heard_value == "magazine_advert":
        where_heard_value = "Advert on Magazine"
    elif where_heard_value == "event":
        where_heard_value = "Event"
    elif where_heard_value == "social_media":
        where_heard_value = "Social Media"
    elif where_heard_value == "travel_agency":
        where_heard_value = "Travel Agency"
    elif where_heard_value == "other":
        where_heard_value = "etc)"

    questions_or_comments_value = lead.questions_or_comments or lead.questions_or_comments_extra_field

    if isinstance(desired_destination_value, str):
        desired_destination_value = [desired_destination_value]
    if how_can_we_help_value == "villa_rental":
        how_can_we_help_value = "I'm interested in a villa rental"
    elif how_can_we_help_value == "property_management":
        how_can_we_help_value = "I would like to know more about property management"
    elif how_can_we_help_value == "travel_agent_inquiry":
        how_can_we_help_value = "I am a travel agent with an inquiry"

    smsMarketing = "Yes" if lead.smsMarketing else "No"
    person_data = {
        'first_name': lead.first_name,
        'last_name': lead.last_name,
        'name': f"Form sent by {lead.first_name} {lead.last_name}".strip(),
        'email': [{'value': lead.email, 'primary': True}],
        'phone': [{'value': lead.phone_number, 'primary': True}] if lead.phone_number else [],
        'marketing_status': 'subscribed' if lead.newsletter else 'unsubscribed',
        "d49e0b562597476d0ae0563849e153dd9030ec3f": desired_destination_value,
        "9b71152696b8c06ebd00379f686db47785b2a7d1": how_can_we_help_value,
        "c9e62b73d9957f9ba3a0e528a14fd83219d30505": where_heard_value,
        "873f1f2e5a02e4b03772844815f90a254b3f1b14": questions_or_comments_value,
        "0661669830067aa6bb4a0ef40ef29b0ad1e30ad8": smsMarketing,
    }
    try:
        response = pipedrive_api.create_person(person_data)
        if response.get('success'):
            logging.info(f"Lead {lead_id} successfully sent to Pipedrive. Pipedrive ID: {response['data']['id']}")
        else:
            logging.error(f"Failed to send Lead {lead_id} to Pipedrive: {response}")
    except Exception as e:
        logging.error(f"Error sending Lead {lead_id} to Pipedrive: {e}")

    if response.get('success'):
        person_id = response['data']['id']
    else:
        logging.error(f"Failed to create person in Pipedrive: {response}")
        return

    deal_data = {
        'title': f"Lead from - {lead.first_name} {lead.last_name}".strip(),
        'person_id': person_id,
        'value': 0,
        'currency': 'USD',
        '6f6d46a3cca8fa33f77f705dd0ab00a8df17c9dd': 61,
    }
    deal_response = pipedrive_api.create_deal(deal_data)

    if not deal_response.get('success'):
        logging.error(f"Failed to create deal in Pipedrive: {deal_response}")
