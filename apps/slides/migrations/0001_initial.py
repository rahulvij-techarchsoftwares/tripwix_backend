import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('photologue', '0013_alter_watermark_image'),
    ]

    operations = [
        migrations.CreateModel(
            name='Slideshow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Slide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='slide_image', verbose_name='Image')),
                (
                    'date_taken',
                    models.DateTimeField(
                        blank=True,
                        help_text='Date image was taken; is obtained from the image EXIF data.',
                        null=True,
                        verbose_name='date taken',
                    ),
                ),
                ('view_count', models.PositiveIntegerField(default=0, editable=False, verbose_name='view count')),
                (
                    'crop_from',
                    models.CharField(
                        blank=True,
                        choices=[
                            ('top', 'Top'),
                            ('right', 'Right'),
                            ('bottom', 'Bottom'),
                            ('left', 'Left'),
                            ('center', 'Center (Default)'),
                        ],
                        default='center',
                        max_length=10,
                        verbose_name='crop from',
                    ),
                ),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                (
                    'effect',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='%(class)s_related',
                        to='photologue.photoeffect',
                        verbose_name='effect',
                    ),
                ),
                (
                    'slideshow',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name='slides', to='slides.slideshow'
                    ),
                ),
            ],
            options={
                'ordering': ('order',),
            },
        ),
    ]
