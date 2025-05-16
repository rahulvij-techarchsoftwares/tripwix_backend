from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('slides', '0003_slide_description'),
    ]

    operations = [
        migrations.AlterField(
            model_name='slide',
            name='image',
            field=models.ImageField(help_text='Max size: 10MB', upload_to='slide_image', verbose_name='Image'),
        ),
        migrations.AlterField(
            model_name='slide',
            name='mobile_image',
            field=models.ImageField(
                blank=True,
                help_text='Max size: 10MB',
                null=True,
                upload_to='slide_image_mobile',
                verbose_name='Mobile Image',
            ),
        ),
    ]
