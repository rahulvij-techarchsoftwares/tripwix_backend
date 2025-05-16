from django.contrib import admin
from django.db import models

from apps.properties.widgets import CustomMceEditorWidget

from .models import Article, Author, Topic


class TopicInline(admin.StackedInline):
    model = Topic
    extra = 1
    formfield_overrides = {
        models.TextField: {'widget': CustomMceEditorWidget},
    }


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'related_destination', 'created_at')
    search_fields = ('title', 'content', 'slug')
    list_filter = ('author', 'related_destination', 'created_at')
    inlines = [TopicInline]
