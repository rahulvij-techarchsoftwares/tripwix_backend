from rest_framework.routers import DefaultRouter

from .views import ArticleViewSet, AuthorViewSet, TopicViewSet

router = DefaultRouter()
router.register(r'articles', ArticleViewSet)
router.register(r'authors', AuthorViewSet)
router.register(r'topics', TopicViewSet)

urlpatterns = router.urls
