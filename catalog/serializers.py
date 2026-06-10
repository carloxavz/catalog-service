from rest_framework import serializers
from .models import Category, Product, Review, ProductImage
import requests
import os
import logging

logger = logging.getLogger(__name__)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'product', 'image', 'created_at']
        read_only_fields = ['created_at']

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')
    # Nombres de todas las categorías (principal + adicionales)
    all_category_names = serializers.SerializerMethodField()
    # IDs de categorías adicionales para lectura
    extra_category_ids = serializers.PrimaryKeyRelatedField(
        source='categories',
        many=True,
        read_only=True
    )
    average_rating = serializers.ReadOnlyField()
    reviews = ReviewSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()
    seller_name = serializers.SerializerMethodField()
    
    stock = serializers.IntegerField(required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock',
            'category', 'category_name', 'extra_category_ids', 'all_category_names',
            'images', 'image', 'seller_id', 'seller_name',
            'average_rating', 'reviews', 'created_at', 'updated_at'
        ]

    def get_all_category_names(self, obj):
        names = [obj.category.name]
        for cat in obj.categories.all():
            if cat.name not in names:
                names.append(cat.name)
        return names

    def get_image(self, obj):
        first_image = obj.images.first()
        if first_image and first_image.image:
            # CloudinaryField.url devuelve la URL pública segura (https)
            return first_image.image.url
        return None

    def get_seller_name(self, obj):
        auth_url = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8001/api/auth')
        try:
            resp = requests.get(f"{auth_url}/users/{obj.seller_id}/public", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('name') or f'Vendedor #{obj.seller_id}'
        except Exception as e:
            logger.warning(f"No se pudo obtener nombre del vendedor {obj.seller_id}: {e}")
        return f'Vendedor #{obj.seller_id}'

    def to_representation(self, instance):
        """
        FUENTE ÚNICA DE VERDAD: Siempre consultamos al microservicio de inventario.
        """
        data = super().to_representation(instance)
        
        # Consultar el microservicio de inventario (Neon DB - billowing-smoke)
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'http://127.0.0.1:8003/api/inventory')
        try:
            # Timeout generoso para asegurar la conexión con Neon
            resp = requests.get(f"{inventory_url}/{instance.id}", timeout=5.0)
            if resp.status_code == 200:
                data['stock'] = resp.json().get('quantity', 0)
            else:
                # Si no existe en inventario, devolvemos 0 (no usamos el valor local)
                data['stock'] = 0
        except Exception as e:
            logger.error(f"FALLO CRÍTICO DE SINCRONIZACIÓN: {str(e)}")
            # En caso de error de red, mostramos 0 para evitar ventas falsas
            # El usuario verá 'Agotado' hasta que el servicio de inventario vuelva
            data['stock'] = 0
        
        return data

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor que cero.")
        return value
