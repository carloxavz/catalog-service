from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ReviewViewSet, ProductImageViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'reviews', ReviewViewSet)
router.register(r'product-images', ProductImageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
