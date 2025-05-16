from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('slides', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='slide',
            name='alt_text_desktop',
            field=models.CharField(blank=True, max_length=140, null=True, verbose_name='Alternative text desktop'),
        ),
        migrations.AddField(
            model_name='slide',
            name='alt_text_mobile',
            field=models.CharField(blank=True, max_length=140, null=True, verbose_name='Alternative text mobile'),
        ),
        migrations.AddField(
            model_name='slide',
            name='mobile_image',
            field=models.ImageField(blank=True, null=True, upload_to='slide_image_mobile', verbose_name='Mobile Image'),
        ),
    ]
