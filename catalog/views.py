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
        
        # Validation: Max 4 images
        if len(images) > 4:
            return Response(
                {"detail": "No se pueden subir más de 4 imágenes por producto."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            product = serializer.save()
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            return Response(self.get_serializer(product).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {"detail": f"Error al crear el producto: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def partial_update(self, request, *args, **kwargs):
        images = request.FILES.getlist('images')
        product = self.get_object()
        
        # Validation: Max 4 images total
        current_images_count = product.images.count()
        if current_images_count + len(images) > 4:
            return Response(
                {"detail": "El producto no puede tener más de 4 imágenes en total."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            return super().partial_update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"Error al actualizar el producto: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def bulk_reduce_stock(self, request):
        import requests
        import os
        items = request.data.get('items', [])
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'http://localhost:8003/api/inventory')
        updated_products = []
        errors = []
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            try:
                # Call inventory-service to reduce stock
                resp = requests.post(f"{inventory_url}/{product_id}/reduce", params={"amount": quantity}, timeout=5)
                if resp.status_code == 200:
                    updated_products.append(product_id)
                else:
                    errors.append(f"Could not reduce stock for product {product_id}: {resp.status_code}")
            except Exception as e:
                errors.append(f"Error calling inventory service for product {product_id}: {str(e)}")
        
        if errors:
            return Response({"errors": errors, "updated": updated_products}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Stock updated via inventory-service", "updated": updated_products}, status=status.HTTP_200_OK)

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
