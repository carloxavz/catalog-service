from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product, Review, ProductImage
from .serializers import CategorySerializer, ProductSerializer, ReviewSerializer, ProductImageSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'price', 'seller_id']
    search_fields = ['name', 'description']
    ordering_filters = ['price', 'created_at']

    def create(self, request, *args, **kwargs):
        images = request.FILES.getlist('images')
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        
        for image in images:
            ProductImage.objects.create(product=product, image=image)
            
        return Response(self.get_serializer(product).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        images = request.FILES.getlist('images')
        product = self.get_object()
        
        # If new images are provided, we might want to clear old ones or just add new ones.
        # For simplicity, let's just add new ones.
        for image in images:
            ProductImage.objects.create(product=product, image=image)
            
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        product = self.get_object()
        data = request.data.copy()
        data['product'] = product.id
        
        # In a real microservice, we would get user_id from a JWT token
        # For now, we expect it in the request body
        serializer = ReviewSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['created_at']
