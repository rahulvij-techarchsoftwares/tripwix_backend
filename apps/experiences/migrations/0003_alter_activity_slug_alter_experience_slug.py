# Generated by Django 4.2.14 on 2024-10-08 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiences', '0002_remove_experience_properties_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='slug',
            field=models.SlugField(unique=True, verbose_name='Url / Handle'),
        ),
        migrations.AlterField(
            model_name='experience',
            name='slug',
            field=models.SlugField(unique=True, verbose_name='Url / Handle'),
        ),
    ]
