from django.core.management.base import BaseCommand
from catalog.models import Product
import requests
import os

class Command(BaseCommand):
    help = 'Syncs all product stock to inventory-service'

    def handle(self, *args, **options):
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'http://127.0.0.1:8003/api/inventory')
        products = Product.objects.all()
        self.stdout.write(f'Found {products.count()} products to sync.')

        for product in products:
            try:
                # Sync stock via PUT (creates or updates)
                resp = requests.put(f"{inventory_url}/{product.id}", json=int(product.stock), timeout=5)
                if resp.status_code in [200, 201]:
                    self.stdout.write(self.style.SUCCESS(f'Synced product {product.id} (Stock: {product.stock})'))
                else:
                    self.stdout.write(self.style.ERROR(f'Failed to sync product {product.id}: {resp.status_code}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error syncing product {product.id}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('Sync completed.'))
