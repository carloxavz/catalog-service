from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Avg

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    seller_id = models.IntegerField()  # Reference to user in login-service
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"

    def save(self, *args, **kwargs):
        old_image = None
        if self.pk:
            try:
                old_image = ProductImage.objects.get(pk=self.pk).image
            except ProductImage.DoesNotExist:
                old_image = None

        super().save(*args, **kwargs)

        if old_image and old_image.name and old_image.name != self.image.name:
            old_image.delete(save=False)

    def delete(self, *args, **kwargs):
        image = self.image
        super().delete(*args, **kwargs)
        if image:
            image.delete(save=False)

class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user_id = models.IntegerField()  # Reference to user in login-service
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for {self.product.name} by User {self.user_id}"
