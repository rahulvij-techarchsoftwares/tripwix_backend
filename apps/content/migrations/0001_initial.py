# Generated by Django 4.2.1 on 2023-08-10 16:08

import django.contrib.postgres.indexes
import django.db.models.deletion
import hashid_field.field
from django.db import migrations, models

import apps.core.fields
import apps.media.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('media', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='Content',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated')),
                (
                    'id',
                    hashid_field.field.HashidAutoField(
                        alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890',
                        min_length=7,
                        prefix='',
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'content_type',
                    models.CharField(
                        choices=[('cnt', 'Content'), ('app', 'App'), ('img', 'Image')], default='cnt', max_length=3, verbose_name='content type'
                    ),
                ),
                ('object_id', models.CharField(max_length=255, null=True)),
                ('unique_name', models.CharField(max_length=255, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('content_text', models.TextField(blank=True, null=True)),
                ('i18n', apps.core.fields.TranslationField(fields=('title', 'content_text'), required_languages=(), virtual_fields=True)),
                ('app_model', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                (
                    'image',
                    apps.media.fields.MediaPhotoForeignKey(
                        blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='media.mediaphoto'
                    ),
                ),
            ],
            options={
                'abstract': False,
                'indexes': [django.contrib.postgres.indexes.HashIndex(fields=['id'], name='content_hashid_idx')],
            },
        ),
    ]
