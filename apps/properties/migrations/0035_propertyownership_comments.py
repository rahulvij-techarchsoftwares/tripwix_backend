# Generated by Django 4.2.14 on 2024-10-01 10:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0034_propertymanager_remarks'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertyownership',
            name='comments',
            field=models.TextField(blank=True, null=True, verbose_name='Comments'),
        ),
    ]
