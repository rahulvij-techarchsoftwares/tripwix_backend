# Generated by Django 4.2.14 on 2024-10-08 12:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('experiences', '0003_alter_activity_slug_alter_experience_slug'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='wishlist',
            name='properties',
        ),
    ]
