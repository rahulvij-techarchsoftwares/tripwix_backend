# Generated by Django 4.2.14 on 2024-10-25 11:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blogs', '0003_delete_topicimage'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='banner',
            field=models.ImageField(blank=True, null=True, upload_to='articles/banners/'),
        ),
        migrations.AddField(
            model_name='article',
            name='thumbnail',
            field=models.ImageField(blank=True, null=True, upload_to='articles/thumbnails/'),
        ),
    ]
