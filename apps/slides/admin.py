from django.contrib import admin
from django.db.models import ImageField

from apps.media.widgets import ImageWidget
from apps.slides.forms import SlideInlineForm
from apps.slides.models import Slide, Slideshow


class SlideInline(admin.StackedInline):
    model = Slide
    extra = 0
    fields = (
        'title',
        'caption',
        'description',
        'cta_text',
        'cta_url',
        'extra_data',
        'order',
        'image',
        'mobile_image',
        'alt_text_desktop',
        'alt_text_mobile',
    )
    ordering = ('order',)
    formfield_overrides = {ImageField: {'widget': ImageWidget}}
    form = SlideInlineForm


@admin.register(Slideshow)
class SlideshowAdmin(admin.ModelAdmin):
    inlines = (SlideInline,)
    list_display = ('title', 'slide_count')
    search_fields = ('title',)
    ordering = ('title',)
    readonly_fields = ('slide_count',)

    @staticmethod
    def slide_count(obj):
        return obj.slides.count()
