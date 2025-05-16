from datetime import date

from django.db import transaction

from apps.properties.models import Property, Rate


class ImportRates(object):

    property_map = {}

    def __init__(self, rates) -> None:
        self.rates = rates

    def create_rate(self, rate):
        try:
            if rate.get('propertyid') not in self.property_map:
                self.property_map[rate.get('propertyid')] = Property.objects.get(reference=rate.get('propertyid'))

            return Rate(
                **{
                    'property': self.property_map[rate.get('propertyid')],
                    'season': rate.get('season'),
                    'from_date': date.fromisoformat(rate.get('fromdate').split('T')[0]),
                    'to_date': date.fromisoformat(rate.get('todate').split('T')[0]),
                    'minimum_nights': rate.get('minnights'),
                    'website_sales_value': rate.get('websalesprice'),
                }
            )
        except Property.DoesNotExist:
            raise Exception('Property with reference %s does not exist' % rate.get('propertyid'))

    def run(self):
        rates = []
        with transaction.atomic():
            for rate in self.rates:
                try:
                    rates.append(self.create_rate(rate))
                except Exception:
                    raise Exception('Property with reference %s does not exist' % rate.get('propertyid'))

            Rate.objects.bulk_create(rates)
