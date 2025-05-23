# Generated by Django 4.2.1 on 2023-08-10 15:50

import django.contrib.postgres.indexes
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import apps.core.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('components', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComponentForm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated')),
                (
                    'slug',
                    models.CharField(
                        help_text="Example: 'some/slug'.",
                        max_length=250,
                        unique=True,
                        validators=[django.core.validators.RegexValidator('^[a-z0-9\\/]+(?:-[a-z0-9\\/]+)*$', 'This value is invalid.')],
                        verbose_name='Url / Handle',
                    ),
                ),
                ('title', models.CharField(max_length=140, verbose_name='Title')),
                (
                    'is_active',
                    models.BooleanField(
                        default=False,
                        help_text='Designates whether this item should be treated as active. Unselect this instead of deleting items.',
                        verbose_name='active',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Form',
                'verbose_name_plural': 'Forms',
            },
        ),
        migrations.CreateModel(
            name='ComponentFormFields',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
                ('slug', models.SlugField(verbose_name='Handle')),
                ('item_o', models.IntegerField(default=0, verbose_name='Sort order')),
                ('is_required', models.BooleanField(default=False, verbose_name='Is required')),
                ('is_multiple', models.BooleanField(default=False, verbose_name='Is multiple')),
                ('i18n', apps.core.fields.TranslationField(fields=('name',), required_languages=(), virtual_fields=True)),
                ('field', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='forms', to='components.componentfield')),
                (
                    'form',
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='form_fields', to='component_forms.componentform'),
                ),
            ],
            options={
                'verbose_name': 'form Field',
                'verbose_name_plural': 'form Fields',
                'ordering': ['item_o'],
                'indexes': [django.contrib.postgres.indexes.GinIndex(fields=['i18n'], name='component_f_i18n_b26277_gin')],
                'unique_together': {('form', 'slug')},
            },
        ),
    ]
