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

    # Module-level cache: seller_id -> name, avoids repeated HTTP calls per request
    _seller_name_cache: dict = {}

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
        seller_id = obj.seller_id
        cache = ProductSerializer._seller_name_cache

        if seller_id in cache:
            return cache[seller_id]

        auth_url = os.getenv('AUTH_SERVICE_URL', 'http://localhost:8001/api/auth')
        try:
            resp = requests.get(f"{auth_url}/users/{seller_id}/public", timeout=3.0)
            if resp.status_code == 200:
                name = resp.json().get('name') or f'Vendedor #{seller_id}'
                cache[seller_id] = name
                return name
        except Exception as e:
            logger.warning(f"No se pudo obtener nombre del vendedor {seller_id}: {e}")

        fallback = f'Vendedor #{seller_id}'
        cache[seller_id] = fallback
        return fallback

    def to_representation(self, instance):
        data = super().to_representation(instance)

        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'http://127.0.0.1:8003/api/inventory')
        try:
            resp = requests.get(f"{inventory_url}/{instance.id}", timeout=5.0)
            if resp.status_code == 200:
                # Inventory has a record — use it as source of truth
                data['stock'] = resp.json().get('quantity', instance.stock)
            elif resp.status_code == 404:
                # Product not yet registered in inventory (e.g. just created)
                # Fall back to local value so the creator sees the correct stock
                data['stock'] = instance.stock
            else:
                data['stock'] = instance.stock
        except Exception as e:
            logger.warning(f"Could not reach inventory-service for product {instance.id}: {e}")
            # Fall back to local value — avoids showing 0 on network errors
            data['stock'] = instance.stock

        return data

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError("El nombre debe tener al menos 3 caracteres.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor que cero.")
        return value
