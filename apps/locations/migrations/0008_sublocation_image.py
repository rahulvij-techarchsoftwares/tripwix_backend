# Generated by Django 4.2.14 on 2024-12-06 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0007_remove_location_experiences'),
    ]

    operations = [
        migrations.AddField(
            model_name='sublocation',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='sublocations/'),
        ),
    ]
