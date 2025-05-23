# Generated by Django 4.2.5 on 2023-10-25 15:28

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('locations', '0003_alter_location_options_alter_sublocation_options'),
        ('properties', '0008_alter_propertyownership_account_type_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyManager',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Name')),
            ],
        ),
        migrations.RemoveField(
            model_name='property',
            name='commission_company',
        ),
        migrations.AlterField(
            model_name='property',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='locations.location', verbose_name='destination'),
        ),
        migrations.AlterField(
            model_name='property',
            name='sublocation',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='locations.sublocation', verbose_name='community'),
        ),
        migrations.AddField(
            model_name='property',
            name='manager',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='properties.propertymanager', verbose_name='Manager'),
        ),
    ]
