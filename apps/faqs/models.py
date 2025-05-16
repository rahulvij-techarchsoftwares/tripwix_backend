# apps/faq/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class FAQCategory(models.Model):
    name = models.CharField(_('Title'), max_length=100)
    slug = models.SlugField(_('Url / Handle'), unique=True)
    is_active = models.BooleanField(_('active'), default=True)

    class Meta:
        verbose_name = _("FAQ Category")
        verbose_name_plural = _("FAQ Categories")

    def __str__(self):
        return self.name

    @classmethod
    def get_model_serializer(cls, obj):
        from apps.faqs.serializers import FAQCategorySerializer

        return FAQCategorySerializer


class FAQ(models.Model):
    category = models.ForeignKey(FAQCategory, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(_('Question'), max_length=250)
    answer = models.TextField(_('Answer'), blank=True)
    item_order = models.IntegerField(_('Order'), default=0)

    class Meta:
        verbose_name = _('FAQ')
        verbose_name_plural = _('FAQs')
        ordering = ['item_order']

    def __str__(self):
        return self.question
