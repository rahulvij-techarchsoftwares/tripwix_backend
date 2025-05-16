import re

from django.db import transaction
from django.utils.text import slugify

from apps.locations.models import City, Country

from .choices import ACCOUNT_TYPE_CHOICES_LIST
from .models import PropertyOwnership


class ImportOwnersTripWix(object):
    @staticmethod
    def get_city(name):
        remarks = ''
        try:
            city = City.objects.get(slug=slugify(name))
        except City.DoesNotExist:
            city = None
            remarks = f'City: {name} does not exists in database\n'

        return city, remarks

    @staticmethod
    def get_country(name):
        remarks = ''
        country = Country.objects.filter(name=name).first()

        if country is None:
            remarks = f'Country: {name} does not exist in database\n'

        return country, remarks

    def get_account_type(self, account_type):
        remarks = ''
        if account_type not in ACCOUNT_TYPE_CHOICES_LIST:
            remarks = 'Account Type: not one of the choices\n'

        return account_type, remarks

    @staticmethod
    def get_phone_number(phone_number):
        remarks = ''
        if phone_number and type(phone_number) is str:
            valid_phone_number = not re.search('[a-zA-Z]', phone_number)
        else:
            valid_phone_number = True

        if not valid_phone_number:
            remarks = 'Phone number: Contains letters\n'

        return phone_number, remarks

    @staticmethod
    def get_zip_code(zip_code):
        remarks = ''

        if not zip_code:
            return '', remarks

        try:
            int(zip_code)
        except ValueError:
            remarks = 'Zip Code: Contains letters\n'

        return zip_code, remarks

    @staticmethod
    def get_preferred_language(preferred_language):
        remarks = ''

        if preferred_language == 'Choose...':
            remarks = 'Preferred Language: Invalid Language\n'

        return preferred_language, remarks

    @staticmethod
    def get_contact_method(contact_method):
        remarks = ''

        if contact_method == 'Choose...':
            remarks = 'Contact Method: Invalid Contact Method\n'

        return contact_method, remarks

    @staticmethod
    def get_onboarding_contact(onboarding_contact):
        remarks = ''

        if onboarding_contact == 'Choose...':
            remarks = 'Onboarding Contact: Invalid Onboarding Contact\n'

        return onboarding_contact, remarks

    @staticmethod
    def get_onboarding_source(onboarding_source):
        remarks = ''

        if onboarding_source == 'Choose...':
            remarks = 'Onboarding Source: Invalid Onboarding Source\n'
        try:
            return onboarding_source.lower().replace(' ', '').replace('.', '_'), remarks
        except:
            raise Exception(f'Error on onboarding_source: {onboarding_source}')

    def save_owners(self, owners):
        property_ownerships = list()
        remarks_fields = [
            'country',
            'zip_code',
            'phone',
            'phone_2',
            'language',
            'contact_method',
            'account_type',
            'city',
        ]
        for owner in owners:
            city, city_remarks = self.get_city(owner.get('city', ''))
            country, country_remarks = self.get_country(owner.get('country', ''))
            zip_code, zip_code_remarks = self.get_zip_code(owner.get('zipCode', ''))
            phone, phone_remarks = self.get_phone_number(owner.get('reservationPhone1', ''))
            phone_2, phone_2_remarks = self.get_phone_number(owner.get('reservationEmail2', ''))
            language, language_remarks = self.get_preferred_language(owner.get('preferredLanguage', ''))
            contact_method, contact_method_remarks = self.get_contact_method(owner.get('preferredContactMethod', ''))
            account_type, account_type_remarks = self.get_account_type(owner.get('accountType', ''))
            onboarding_contact, onboarding_contact_remarks = self.get_onboarding_contact(
                owner.get('onboardingContact', '')
            )
            onboarding_source, onboarding_source_remarks = self.get_onboarding_source(owner.get('onboardingSource', ''))

            first_name = owner.get('accountFirstName', '')
            last_name = owner.get('accountLastName', '')
            full_name = f'{first_name} {last_name}'
            account_id = owner.get('accountId')
            data = {
                'id': account_id,
                'account_id': account_id,
                'last_name': last_name,
                'first_name': first_name,
                'language': language,
                'email': owner.get('reservationEmail1', ''),
                'phone': phone,
                'notes': owner.get('contactNotes', ''),
                'contact_method': contact_method,
                'email_2': owner.get('reservationEmail2', ''),
                'phone_2': phone_2,
                'notes_2': owner.get('contactNotes2', ''),
                'street': owner.get('streetNameNumber', ''),
                'city': city,
                'state': owner.get('stateProvince', ''),
                'zip_code': zip_code,
                'country': country,
                'account_type': account_type,
                'company_legal_name': owner.get('companyLegalName', ''),
                'tax_id': owner.get('taxId', ''),
                'onboarding_contact': onboarding_contact,
                'onboarding_source': onboarding_source,
                'name': full_name,
                'slug': f'{slugify(full_name)[:40]}{account_id}',
                'comments': owner.get('comments', ''),
            }

            # Update Remarks
            remarks = ''
            for field in remarks_fields:
                remarks += locals()[f'{field}_remarks']

            data['remarks'] = remarks

            property_ownerships.append(PropertyOwnership(**data))

        PropertyOwnership.objects.bulk_create(
            property_ownerships,
            update_conflicts=True,
            update_fields=[
                'last_name',
                'first_name',
                'language',
                'email',
                'phone',
                'notes',
                'contact_method',
                'email_2',
                'phone_2',
                'notes_2',
                'street',
                'city',
                'state',
                'zip_code',
                'country',
                'account_type',
                'company_legal_name',
                'tax_id',
                'onboarding_contact',
                'onboarding_source',
                'name',
                'slug',
                'comments',
            ],
            unique_fields=['account_id'],
        )

    @transaction.atomic
    def run(self, owners_list):
        self.save_owners(owners_list)
        return True
