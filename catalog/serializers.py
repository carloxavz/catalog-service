from rest_framework import serializers
from .models import Category, Product, Review, ProductImage

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

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock', 
            'category', 'category_name', 'images', 'seller_id', 
            'average_rating', 'reviews', 'created_at', 'updated_at'
        ]
