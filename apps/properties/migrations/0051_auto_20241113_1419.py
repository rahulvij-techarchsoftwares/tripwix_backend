# Generated by Django 4.2.14 on 2024-11-12 14:17

from pathlib import Path

from django.db import migrations, models


def populate_ambassador_and_tagline(apps, schema_editor):
    import json

    from django.core.exceptions import ObjectDoesNotExist

    Property = apps.get_model('properties', 'Property')
    Ambassador = apps.get_model('properties', 'Ambassador')


    migration_dir = Path(__file__).parent.parent.parent.parent
    json_path = migration_dir / 'docs' / 'properties.json'

    if not json_path.exists():
        raise FileNotFoundError(f"Arquivo 'properties.json' não encontrado em {json_path}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        property_id = item.get('propertyId') 
        if not property_id:
            print("Ignorando item sem 'propertyId'.")
            continue

        ambassador_name = item.get('ambassadorName')
        tagline = item.get('tagline')

        try:
            property_obj = Property.objects.get(name=property_id)

            if ambassador_name:
                ambassador_obj, created = Ambassador.objects.get_or_create(name=ambassador_name)
                property_obj.ambassador = ambassador_obj
                if created:
                    print(f"Ambassador '{ambassador_name}' criado.")
                else:
                    print(f"Ambassador '{ambassador_name}' encontrado.")

            if tagline:
                property_obj.tagline = tagline

            property_obj.save()
            print(f"Property '{property_obj.name}' atualizado com sucesso.")
        except ObjectDoesNotExist:
            print(f"Property com name '{property_id}' não encontrado.")
            continue 

class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0050_property_permit_id'), 
    ]

    operations = [
        migrations.AlterField(
            model_name='ambassador',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='ambassador',
            name='photo',
            field=models.ImageField(blank=True, null=True, upload_to='ambassadors/'),
        ),
        migrations.RunPython(populate_ambassador_and_tagline, reverse_code=migrations.RunPython.noop),
    ]