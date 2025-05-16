from rest_framework import serializers

from .models import Article, Author, Topic


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['id', 'name', 'description', 'avatar']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'title', 'content']


class ArticleSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    related_destination = serializers.StringRelatedField()
    tag = serializers.CharField(source='get_tag_display', read_only=True)

    class Meta:
        model = Article
        fields = [
            'id',
            'title',
            'slug',
            'tag',
            'content',
            'author',
            'related_destination',
            'created_at',
            'thumbnail',
            'banner',
            'publication_date',
            'is_active',
        ]


class ArticleDetailSerializer(ArticleSerializer):
    topics = TopicSerializer(many=True, read_only=True)
    next_article = serializers.SerializerMethodField()
    previous_article = serializers.SerializerMethodField()

    class Meta(ArticleSerializer.Meta):
        fields = ArticleSerializer.Meta.fields + ['topics', 'next_article', 'previous_article']

    def get_next_article(self, obj):
        article = Article.objects.filter(created_at__gt=obj.created_at, is_active=True).order_by('created_at').first()
        if article:
            return article.slug
        return None

    def get_previous_article(self, obj):
        article = Article.objects.filter(created_at__lt=obj.created_at, is_active=True).order_by('-created_at').first()
        if article:
            return article.slug
        return None
