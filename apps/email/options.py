from django import forms
from django.template import Context, Template
from django.template.loader import render_to_string


class AlreadyRegistered(Exception):
    pass


class EmailDefinition(forms.Form):
    html_template = None
    text_template = None

    @classmethod
    def comp_name(cls):
        return f'{cls.__module__}.{cls.__name__}'

    @classmethod
    def sample_context(cls, bank):
        """
        Sample Context is for email previews, use the bank to get common context options
        """
        return {}

    def __init__(self, *args, **kwargs):
        self.context = kwargs.pop('context') if 'context' in kwargs else {}
        self.lang = kwargs.pop('lang') if 'lang' in kwargs else None
        self.instance = kwargs.get('instance')
        if not self.instance:
            self.instance = self.get_instance_from_db()
        initial = self.instance.data
        if 'initial' in kwargs:
            kwargs['initial'].update(initial)
        else:
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def get_base_context(self):
        context = self.context.copy()
        # handle translations
        trans = self.instance.translations.filter(is_active=True, lang=self.lang).first() if self.lang else None
        if trans:
            context.update(trans.data or self.instance.data)
        else:
            context.update(self.instance.data or {})
        return context

    def get_context(self):
        context = self.get_base_context()

        for field_name, field in self.declared_fields.items():
            if field_name not in context:
                context[field_name] = field.initial

        for key, value in context.items():
            # check if we need to render template variables or tags
            if isinstance(value, str) and ('{{' in value or '{%' in value):
                template = Template(value)
                context[key] = template.render(Context(context))

        return context

    def get_subject(self):
        subject_field = self.fields.get('subject', None)
        fallback_subject = subject_field.initial if subject_field else None
        fallback_subject = self.instance.data.get('subject') if self.instance.data else fallback_subject
        subject = getattr(self, 'subject', fallback_subject)

        if subject:
            template = Template(subject)
            return template.render(Context(self.get_context()))

        return subject

    def get_text_content(self):
        if self.text_template:
            return render_to_string(self.text_template, self.get_context())
        return None

    def get_html_content(self):
        if self.html_template:
            return render_to_string(self.html_template, self.get_context())
        return None

    def get_instance_from_db(self):
        from apps.email.models import EmailDefinitionModel

        original = definitions.get(self.comp_name())
        obj, _created = EmailDefinitionModel.objects.get_or_create(
            module_path=self.comp_name(),
            defaults={'name': original.get('name', original.get('definition').__name__)},
        )
        return obj

    def allow_send(self, recipients):
        if not recipients:
            return False
        # TODO: maybe check if specific emails can be sent
        return self.instance.allow_send

    def save_data(self):
        data = self.cleaned_data.copy()
        if 'allow_send' in data:
            data.pop('allow_send')
        return data


class EmailDefinitions:
    def __init__(self, name='app_email_definitions'):
        self._registry = {}
        self.name = name

    def all(self):
        return self._registry

    def get(self, comp_name):
        return self._registry[comp_name]

    def register(self, name, email_def, **options):
        if not issubclass(email_def, EmailDefinition):
            raise ValueError(f"email_def class {email_def} must subclass EmailDefinition")

        comp_name = email_def.comp_name()
        if comp_name in self._registry:
            msg = f'The EmailDefinition {comp_name} is already registered '
            raise AlreadyRegistered(msg)

        self._registry[comp_name] = {**options, 'definition': email_def, 'name': name}


definitions = EmailDefinitions()
