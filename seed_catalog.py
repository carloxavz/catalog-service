import os
import django
from django.core.files import File

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'catalog_config.settings')
django.setup()

from catalog.models import Category, Product, ProductImage

def seed():
    print("Starting seeding process...")

    # Categories
    categories_data = [
        {'name': 'Electrónica', 'slug': 'electronica'},
        {'name': 'Moda', 'slug': 'moda'},
        {'name': 'Hogar', 'slug': 'hogar'},
        {'name': 'Deportes', 'slug': 'deportes'},
    ]

    categories = {}
    for cat_data in categories_data:
        cat, created = Category.objects.get_or_create(slug=cat_data['slug'], defaults={'name': cat_data['name']})
        categories[cat_data['slug']] = cat
        if created:
            print(f"Created category: {cat.name}")
        else:
            print(f"Category already exists: {cat.name}")

    # Products
    products_data = [
        {
            'name': 'Smartphone Pro X',
            'description': 'Un smartphone de última generación con pantalla OLED de 6.7 pulgadas, triple cámara de 50MP y batería de larga duración. Perfecto para fotografía y juegos.',
            'price': 899.99,
            'stock': 50,
            'category': categories['electronica'],
            'image_filename': 'smartphone.png'
        },
        {
            'name': 'Smartwatch Ultra',
            'description': 'Reloj inteligente con seguimiento de salud avanzado, GPS integrado y resistencia al agua. Estilo elegante con correa de cuero.',
            'price': 249.50,
            'stock': 100,
            'category': categories['electronica'],
            'image_filename': 'smartwatch.png'
        },
        {
            'name': 'Zapatillas Urbanas Blancas',
            'description': 'Zapatillas de cuero sintético con diseño minimalista. Cómodas para el uso diario y fáciles de combinar con cualquier outfit.',
            'price': 75.00,
            'stock': 200,
            'category': categories['moda'],
            'image_filename': 'sneakers.png'
        },
        {
            'name': 'Cafetera Espresso Premium',
            'description': 'Prepara el mejor café en casa con esta cafetera de bomba de 15 bares. Incluye vaporizador de leche para cappuccinos perfectos.',
            'price': 159.99,
            'stock': 30,
            'category': categories['hogar'],
            'image_filename': 'espresso.png'
        },
        {
            'name': 'Bicicleta de Montaña R29',
            'description': 'Bicicleta robusta con cuadro de aluminio, frenos de disco hidráulicos y 21 velocidades. Ideal para senderos y aventuras al aire libre.',
            'price': 450.00,
            'stock': 15,
            'category': categories['deportes'],
            'image_filename': 'bike.png'
        }
    ]

    seller_id = 1  # Default seller ID

    for p_data in products_data:
        product, created = Product.objects.get_or_create(
            name=p_data['name'],
            defaults={
                'description': p_data['description'],
                'price': p_data['price'],
                'stock': p_data['stock'],
                'category': p_data['category'],
                'seller_id': seller_id
            }
        )
        
        if created:
            print(f"Created product: {product.name}")
            # Add image
            image_path = os.path.join('media', 'products', p_data['image_filename'])
            if os.path.exists(image_path):
                with open(image_path, 'rb') as f:
                    product_image = ProductImage(product=product)
                    product_image.image.save(p_data['image_filename'], File(f), save=True)
                print(f"  Added image for {product.name}")
        else:
            print(f"Product already exists: {product.name}")

    print("Seeding completed successfully!")

if __name__ == "__main__":
    seed()
