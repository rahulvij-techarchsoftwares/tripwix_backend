from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('slides', '0002_slide_alt_text_desktop_slide_alt_text_mobile_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='slide',
            name='description',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
