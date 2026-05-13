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
    average_rating = serializers.ReadOnlyField()
    reviews = ReviewSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    image = serializers.SerializerMethodField()
    
    # Stock es ahora un campo que NO se persiste en la tabla de productos del catálogo
    # pero se maneja en el serializador para comunicación con el front y el inventory-service
    stock = serializers.IntegerField(required=False)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock', 
            'category', 'category_name', 'images', 'image', 'seller_id', 
            'average_rating', 'reviews', 'created_at', 'updated_at'
        ]

    def get_image(self, obj):
        first_image = obj.images.first()
        if first_image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(first_image.image.url)
            return first_image.image.url
        return None

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
