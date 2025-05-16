from django.db import models
from photologue.models import IMAGE_FIELD_MAX_LENGTH, ImageModel, get_storage_path


class Slideshow(models.Model):
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

    @classmethod
    def get_model_serializer(cls, page):
        from apps.slides.api.v1.serializers import SliderSerializer

        return SliderSerializer

    class Menu:
        icon = 'fa-video'


class Slide(ImageModel):
    image = models.ImageField(
        max_length=IMAGE_FIELD_MAX_LENGTH, upload_to=get_storage_path, help_text='Max size: 10MB', blank=True, null=True
    )
    title = models.CharField(max_length=255, blank=True)
    caption = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    cta_text = models.CharField(max_length=255, blank=True)
    cta_url = models.URLField(blank=True)
    extra_data = models.JSONField(blank=True, null=True, help_text='JSON data for custom slide types')
    order = models.PositiveIntegerField(default=0)
    slideshow = models.ForeignKey(Slideshow, related_name='slides', on_delete=models.CASCADE)
    mobile_image = models.ImageField(
        'Mobile Image', upload_to='slide_image_mobile', null=True, blank=True, help_text='Max size: 10MB'
    )
    alt_text_desktop = models.CharField('Alternative text desktop', blank=True, null=True, max_length=140)
    alt_text_mobile = models.CharField('Alternative text mobile', blank=True, null=True, max_length=140)

    class Meta:
        ordering = ('order',)

    def __str__(self):
        return self.caption

    @classmethod
    def get_model_serializer(cls, page):
        from apps.slides.api.v1.serializers import SliderItemSerializer

        return SliderItemSerializer
