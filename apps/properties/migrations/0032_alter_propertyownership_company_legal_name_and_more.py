# Generated by Django 4.2.14 on 2024-09-30 23:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0031_alter_propertyownership_phone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyownership',
            name='company_legal_name',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Company Name'),
        ),
        migrations.AlterField(
            model_name='propertyownership',
            name='onboarding_contact',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Onboarding Contact'),
        ),
        migrations.AlterField(
            model_name='propertyownership',
            name='phone_2',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Reservation Phone 2'),
        ),
        migrations.AlterField(
            model_name='propertyownership',
            name='state',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='State and Province'),
        ),
        migrations.AlterField(
            model_name='propertyownership',
            name='street',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Street Name and Number'),
        ),
    ]
