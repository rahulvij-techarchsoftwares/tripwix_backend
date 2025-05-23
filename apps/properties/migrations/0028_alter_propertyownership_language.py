# Generated by Django 4.2.14 on 2024-09-09 10:43

from django.db import migrations, models


def fix_language(apps, schema_editor):
    PropertyOwnership = apps.get_model('properties', 'PropertyOwnership')
    slugs = ('en-us', 'en-gb', 'pt-pt', 'pt-br')
    for po in PropertyOwnership.objects.all():
        if not po.language:
            continue
        if po.language.lower() in slugs:
            po.language = po.language.replace('-', '_')
        elif po.language.lower() == 'spanish':
            po.language = 'es'
        elif po.language.lower() == 'italian':
            po.language = 'it'
        else:
            po.language = 'other'
        po.save()


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0027_alter_propertyownership_contact_method'),
    ]

    operations = [
        migrations.RunPython(fix_language, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='propertyownership',
            name='language',
            field=models.CharField(
                blank=True,
                choices=[
                    ('en_us', 'en-us'),
                    ('en_gb', 'en-gb'),
                    ('pt_pt', 'pt-pt'),
                    ('pt_br', 'pt-br'),
                    ('es', 'es'),
                    ('fr', 'fr'),
                    ('it', 'it'),
                    ('tr', 'tr'),
                    ('other', 'Other'),
                ],
                max_length=5,
                null=True,
                verbose_name='Preferred Language',
            ),
        ),
    ]
