from django import forms

from apps.slides.models import Slide
from apps.slides.utils import validate_image_size


class SlideInlineForm(forms.ModelForm):
    class Meta:
        model = Slide
        fields = '__all__'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        max_size = 10 * 1024 * 1024
        verbose_size = '10 megabytes'
        validate_image_size(image, max_size, verbose_size)
        return image

    def clean_mobile_image(self):
        mobile_image = self.cleaned_data.get('mobile_image')
        max_size = 10 * 1024 * 1024
        verbose_size = '10 megabytes'
        validate_image_size(mobile_image, max_size, verbose_size)
        return mobile_image
