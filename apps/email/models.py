from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AbstractCreatedUpdatedDateMixin


class EmailDefinitionModel(AbstractCreatedUpdatedDateMixin):
    name = models.CharField(
        _('Name'),
        editable=False,
        max_length=250,
    )

    module_path = models.CharField('Module Path', editable=False, max_length=250, unique=True)

    data = models.JSONField(
        null=True,
        blank=True,
    )

    allow_send = models.BooleanField(
        _('Allow sending this type of emails?'), default=True, help_text=_("Designate if this email can be sent out.")
    )

    last_sent_email_ts = models.DateTimeField(
        _('Latest email date'),
        null=True,
        blank=True,
        editable=False,
    )

    last_sent_email_to = models.CharField(
        _('Latest email'),
        null=True,
        blank=True,
        max_length=250,
        editable=False,
    )

    class Meta:
        verbose_name = _("Email Definition")
        verbose_name_plural = _("Email Definitions")

    class Menu:
        icon = 'fas fa-envelope'

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"EmailDefinitionModel('{self.name}', '{self.module_path}','{self.data}', '{self.allow_send}',"
            f" '{self.last_sent_email_ts}', '{self.last_sent_email_to}')"
        )


class EmailDefinitionTranslationModel(AbstractCreatedUpdatedDateMixin):
    email_definition = models.ForeignKey(EmailDefinitionModel, related_name='translations', on_delete=models.CASCADE)
    lang = models.CharField(max_length=32, choices=settings.LANGUAGES)
    data = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(_('Is Active'), default=False)

    def __str__(self):
        return f'Email Def #{self.email_definition_id} translation ({self.lang})'

    class Meta:
        unique_together = ['email_definition', 'lang']
        verbose_name = _("Translation")
        verbose_name_plural = _("Translations")
        ordering = [
            '-is_active',
            'lang',
        ]
