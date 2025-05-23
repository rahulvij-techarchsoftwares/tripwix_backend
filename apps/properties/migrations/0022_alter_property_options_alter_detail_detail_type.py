# Generated by Django 4.2.13 on 2024-07-03 13:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0021_alter_detail_detail_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='property',
            options={'ordering': ('item_o',), 'permissions': (('can_publish_property', 'Can Publish Property'), ('can_change_vat_rate', 'Can Change Property VAT Rate')), 'verbose_name': 'Property', 'verbose_name_plural': 'Properties'},
        ),
        migrations.AlterField(
            model_name='detail',
            name='detail_type',
            field=models.CharField(choices=[('text', 'Text'), ('trans_text', 'Translatable Text'), ('boolean', 'Boolean'), ('option', 'Option'), ('options', 'Options'), ('date', 'Date'), ('time', 'Time'), ('number', 'Number'), ('integer', 'Integer'), ('color', 'Color'), ('description', 'Description'), ('trans_description', 'Translatable Description'), ('integer_options', 'Integer Options'), ('rating', 'Rating'), ('videos', 'Videos'), ('image', 'Image'), ('360_image', 'Image 360'), ('integer_sum', 'Integer with Sum'), ('number_with_value_type_selector', 'Number with Value Type Selector'), ('country_vat_choices', 'Country VAT Choices')], max_length=31, verbose_name='detail type'),
        ),
    ]
