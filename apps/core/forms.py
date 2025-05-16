import six
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.db.models.query import QuerySet

from apps.core.widgets import SortedCheckboxSelectMultiple


class OtpSetupForm(AuthenticationForm):
    def clean(self):
        self.cleaned_data = super().clean()

        user = self.get_user()
        from django_otp import devices_for_user
        from django_otp.plugins.otp_totp.models import TOTPDevice as OTPDevice

        devices = list(devices_for_user(user, confirmed=None))
        # create first device, for now only supports otp_totp
        if not devices:
            device = OTPDevice.objects.create(user=user, name=f"{user.username}")

            try:
                import qrcode
                import qrcode.image.svg

                img = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgImage)
                self.qrcode = str(img.to_string().decode("utf8"))
            except ImportError:
                pass

            self.user_device = device
            raise forms.ValidationError("Setup your Two Factor Device", code='setup_two_factor_device')

        return self.cleaned_data


class SortedMultipleChoiceField(forms.ModelMultipleChoiceField):
    widget = SortedCheckboxSelectMultiple

    def clean(self, value):
        queryset = super().clean(value)
        if value is None or not isinstance(queryset, QuerySet):
            return queryset

        # GIVE NEW ORDER
        object_list = dict((str(key), value) for key, value in six.iteritems(queryset.in_bulk(value)))
        return [object_list[str(pk)] for pk in value]

    def _has_changed(self, initial, data):
        if initial is None:
            initial = []
        if data is None:
            data = []
        if len(initial) != len(data):
            return True
        initial_set = [force_str(value) for value in self.prepare_value(initial)]
        data_set = [force_str(value) for value in data]
        return data_set != initial_set
