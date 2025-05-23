# Generated by Django 4.2.1 on 2023-08-09 18:24

import django.contrib.postgres.indexes
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import apps.core.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('components', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated')),
                (
                    'seo_title',
                    models.CharField(
                        blank=True, help_text='Leave blank to use the default title.', max_length=70, null=True, verbose_name='SEO Title'
                    ),
                ),
                (
                    'seo_description',
                    models.CharField(
                        blank=True,
                        help_text='Leave blank to use the default description.',
                        max_length=155,
                        null=True,
                        verbose_name='SEO Description',
                    ),
                ),
                (
                    'seo_image',
                    models.ImageField(
                        blank=True, help_text='Suggested size: (W:1080px, H:1080px)', null=True, upload_to='seo_images', verbose_name='SEO Image'
                    ),
                ),
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
                (
                    'is_active',
                    models.BooleanField(
                        default=False,
                        help_text='Designates whether this item should be treated as active. Unselect this instead of deleting items.',
                        verbose_name='active',
                    ),
                ),
                (
                    'publication_date',
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        help_text='When this item should be published.',
                        verbose_name='publication date',
                    ),
                ),
                ('fields_data_json', models.JSONField(blank=True, null=True, verbose_name='Data')),
                ('title', models.CharField(max_length=140, verbose_name='Title')),
                (
                    'i18n',
                    apps.core.fields.TranslationField(
                        fields=('title', 'slug', 'seo_title', 'seo_description'), required_languages=(), virtual_fields=True
                    ),
                ),
                ('collection_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='components.collectiontype')),
            ],
            options={
                'verbose_name': 'Page',
                'verbose_name_plural': 'Pages',
                'db_table': 'pages_page',
                'indexes': [
                    django.contrib.postgres.indexes.GinIndex(fields=['fields_data_json'], name='pages_page_fields__e58695_gin'),
                    django.contrib.postgres.indexes.GinIndex(fields=['i18n'], name='pages_page_i18n_feaa6a_gin'),
                ],
            },
        ),
    ]
