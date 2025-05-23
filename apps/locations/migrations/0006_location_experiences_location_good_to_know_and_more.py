# Generated by Django 4.2.14 on 2024-10-14 09:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('experiences', '0006_remove_experience_destination'),
        ('locations', '0005_countryvatrate'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='experiences',
            field=models.ManyToManyField(blank=True, related_name='locations', to='experiences.experience'),
        ),
        migrations.AddField(
            model_name='location',
            name='good_to_know',
            field=models.TextField(blank=True, verbose_name='Good to Know'),
        ),
        migrations.AddField(
            model_name='location',
            name='guide_description',
            field=models.TextField(blank=True, verbose_name='Guide Description'),
        ),
        migrations.AddField(
            model_name='location',
            name='how_to_get_there',
            field=models.CharField(blank=True, max_length=255, verbose_name='How to Get There'),
        ),
        migrations.AddField(
            model_name='location',
            name='when_to_leave',
            field=models.CharField(blank=True, max_length=100, verbose_name='When to Leave'),
        ),
    ]
