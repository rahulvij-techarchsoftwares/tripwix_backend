# Generated by Django 4.2.14 on 2025-02-20 11:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0068_alter_property_default_price_eur'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='property',
            index=models.Index(fields=['item_o'], name='property_item_o_idx'),
        ),
    ]
