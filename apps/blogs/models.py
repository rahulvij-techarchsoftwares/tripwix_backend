from django.db import models
from django.utils import timezone

from apps.core.models import AbstractCreatedUpdatedDateMixin
from apps.locations.models import Location


class Author(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='authors/', blank=True, null=True)

    def __str__(self):
        return self.name


class Article(AbstractCreatedUpdatedDateMixin):
    CATEGORY_CHOICES = [
        ('beautiful_destinations', 'Beautiful Destinations'),
        ('holiday_intel', 'Holiday Intel'),
        ('exploring_our_homes', 'Exploring Our Homes'),
        ('city_guides', 'City Guides'),
        ('our_catalogs', 'Our Catalogs'),
        ('about_tripwix', 'About Tripwix'),
        ('amazing_art_awards', 'Amazing Art Awards'),
        ('awesome_adventures', 'Awesome Adventures'),
        ('beach_breaks', 'Beach Breaks'),
        ('cultural_customs', 'Cultural Customs'),
        ('european_escapes', 'European Escapes'),
        ('fabulous_festivals', 'Fabulous Festivals'),
        ('family_fun', 'Family Fun'),
        ('family_time', 'Family Time'),
        ('golf_getaways', 'Golf Getaways'),
        ('guest_reviews', 'Guest Reviews'),
        ('incredible_italy', 'Incredible Italy'),
        ('local_crafts', 'Local Crafts'),
        ('local_experiences', 'Local Experiences'),
        ('luxury_real_estate', 'Luxury Real Estate'),
        ('luxury_wellness_travel', 'Luxury Wellness Travel'),
        ('marvelous_mexico', 'Marvelous Mexico'),
        ('music_and_nightlife', 'Music and Nightlife'),
        ('natural_wonders', 'Natural Wonders'),
        ('party_places_and_events', 'Party Places and Events'),
        ('pretty_portugal', 'Pretty Portugal'),
        ('property_management', 'Property Management'),
        ('regional_recipes', 'Regional Recipes'),
        ('relaxation', 'Relaxation'),
        ('relaxing_retreats', 'Relaxing Retreats'),
        ('remarkable_restaurants', 'Remarkable Restaurants'),
        ('riverboat_cruise', 'Riverboat Cruise'),
        ('romantic_respites', 'Romantic Respites'),
        ('sunny_spain', 'Sunny Spain'),
        ('superb_shopping', 'Superb Shopping'),
        ('tempting_turkey', 'Tempting Turkey'),
        ('travel_tips', 'Travel Tips'),
        ('whimsical_weddings', 'Whimsical Weddings'),
    ]

    title = models.CharField(max_length=255)
    tag = models.CharField(max_length=50, choices=CATEGORY_CHOICES, null=True, blank=True)
    slug = models.SlugField(max_length=255, unique=True)
    is_active = models.BooleanField(default=False)
    content = models.TextField(null=True, blank=True)
    author = models.ForeignKey(Author, related_name='articles', on_delete=models.CASCADE, null=True, blank=True)
    related_destination = models.ForeignKey(
        Location, related_name='articles', on_delete=models.SET_NULL, null=True, blank=True
    )
    thumbnail = models.ImageField(upload_to='articles/thumbnails/', blank=True, null=True)
    banner = models.ImageField(upload_to='articles/banners/', blank=True, null=True)
    is_active = models.BooleanField(default=False)
    publication_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.is_active and not self.publication_date:
            self.publication_date = timezone.now()
        super().save(*args, **kwargs)

    @classmethod
    def get_model_serializer(cls, obj):
        from .serializers import ArticleSerializer

        return ArticleSerializer

    class Meta:
        ordering = ['-created_at']


class Topic(models.Model):
    article = models.ForeignKey(Article, related_name='topics', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    content = models.TextField()

    def __str__(self):
        return f"{self.title} ({self.article.title})"
