from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Product, Review, ProductImage
from .serializers import CategorySerializer, ProductSerializer, ReviewSerializer, ProductImageSerializer
import requests
import os
from django.db import transaction

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = None
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'price', 'seller_id']
    search_fields = ['name', 'description']
    ordering_filters = ['price', 'created_at']

    def sync_stock_to_inventory(self, product_id, quantity):
        """Helper to sync stock value to inventory-service (Neon DB)"""
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'https://microservicio-6-inventory-service.onrender.com/api/inventory')
        try:
            # PUT en el microservicio de inventario
            resp = requests.put(f"{inventory_url}/{product_id}", json=int(quantity), timeout=5)
            if resp.status_code not in [200, 201]:
                print(f"Error al sincronizar con inventario: {resp.status_code}")
                return False
            return True
        except Exception as e:
            print(f"Fallo de conexión con inventario: {str(e)}")
            return False

    def create(self, request, *args, **kwargs):
        images = request.FILES.getlist('images')
        # Categorías adicionales — pueden venir como lista de IDs en el FormData
        extra_category_ids = request.data.getlist('extra_categories', [])
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            with transaction.atomic():
                product = serializer.save()
                
                # Asignar categorías adicionales
                if extra_category_ids:
                    from .models import Category as Cat
                    cats = Cat.objects.filter(id__in=[int(i) for i in extra_category_ids if i])
                    product.categories.set(cats)

                # Sincronizar Stock Inmediatamente
                stock_value = request.data.get('stock')
                if stock_value is not None:
                    self.sync_stock_to_inventory(product.id, stock_value)

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
        extra_category_ids = request.data.getlist('extra_categories', [])
        
        try:
            with transaction.atomic():
                stock_value = request.data.get('stock')
                if stock_value is not None:
                    # Sincronizar con inventory — no bloquear si falla
                    self.sync_stock_to_inventory(product.id, stock_value)

                # Actualizar categorías adicionales si se enviaron
                if extra_category_ids:
                    from .models import Category as Cat
                    cats = Cat.objects.filter(id__in=[int(i) for i in extra_category_ids if i])
                    product.categories.set(cats)
                elif 'extra_categories' in request.data:
                    # Lista vacía explícita — limpiar todas las adicionales
                    product.categories.clear()

                for image in images:
                    ProductImage.objects.create(product=product, image=image)
                
                return super().partial_update(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"Error al actualizar: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def sync_inventory(self, request):
        """
        POST /api/catalog/products/sync_inventory/
        Syncs all product stock values to inventory-service.
        Useful when inventory-service has no records (e.g. after fresh deploy).
        """
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'https://microservicio-6-inventory-service.onrender.com/api/inventory')
        products = Product.objects.all()
        synced = []
        errors = []

        for product in products:
            try:
                resp = requests.put(
                    f"{inventory_url}/{product.id}",
                    json=int(product.stock),
                    timeout=5
                )
                if resp.status_code in [200, 201]:
                    synced.append(product.id)
                else:
                    errors.append({"product_id": product.id, "status": resp.status_code})
            except Exception as e:
                errors.append({"product_id": product.id, "error": str(e)})

        return Response({
            "synced": len(synced),
            "synced_ids": synced,
            "errors": errors,
        }, status=status.HTTP_200_OK if not errors else status.HTTP_207_MULTI_STATUS)

    @action(detail=False, methods=['post'])
    def bulk_reduce_stock(self, request):
        items = request.data.get('items', [])
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'https://microservicio-6-inventory-service.onrender.com/api/inventory')
        updated_products = []
        errors = []
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            try:
                # El inventario es el que descuenta de forma persistente
                resp = requests.post(f"{inventory_url}/{product_id}/reduce", params={"amount": quantity}, timeout=5)
                
                if resp.status_code == 200:
                    # También actualizamos localmente solo como sombra/caché
                    try:
                        p = Product.objects.get(id=product_id)
                        p.stock = resp.json().get('quantity', p.stock - int(quantity))
                        p.save()
                        updated_products.append(product_id)
                    except Product.DoesNotExist:
                        pass
                else:
                    errors.append(f"Fallo en inventario para {product_id}")
            except Exception as e:
                errors.append(f"Error de conexión: {str(e)}")
        
        if errors:
            return Response({"errors": errors, "updated": updated_products}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"message": "Sincronización exitosa", "updated": updated_products}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def bulk_restore_stock(self, request):
        items = request.data.get('items', [])
        inventory_url = os.getenv('INVENTORY_SERVICE_URL', 'https://microservicio-6-inventory-service.onrender.com/api/inventory')
        
        for item in items:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            try:
                resp = requests.post(f"{inventory_url}/{product_id}/restore", params={"amount": quantity}, timeout=5)
                if resp.status_code == 200:
                    try:
                        p = Product.objects.get(id=product_id)
                        p.stock = resp.json().get('quantity', p.stock + int(quantity))
                        p.save()
                    except Product.DoesNotExist:
                        pass
            except Exception:
                pass
        
        return Response({"message": "Restauración enviada a inventario"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        product = self.get_object()
        data = request.data.copy()
        data['product'] = product.id
        serializer = ReviewSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def seller_info(self, request):
        """
        Devuelve nombre del vendedor y sus estadísticas de ventas.
        GET /api/products/seller_info/?seller_id=5
        """
        seller_id = request.query_params.get('seller_id')
        if not seller_id:
            return Response({'error': 'seller_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Nombre del vendedor desde Auth Service
        auth_url = os.getenv('AUTH_SERVICE_URL', 'https://microservicio-1-auth-service.onrender.com/api/auth')
        seller_name = f'Vendedor #{seller_id}'
        for attempt in range(3):
            try:
                resp = requests.get(f"{auth_url}/users/{seller_id}/public", timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    seller_name = data.get('name') or seller_name
                    break
            except Exception as e:
                print(f"Intento {attempt + 1} fallido para obtener nombre del vendedor {seller_id}: {e}")
                if attempt < 2:
                    import time
                    time.sleep(1)

        # 2. Productos del vendedor o producto específico
        product_id = request.query_params.get('product_id')
        if product_id:
            try:
                product_ids = [int(product_id)]
            except ValueError:
                return Response({'error': 'product_id inválido'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            product_ids = list(
                Product.objects.filter(seller_id=seller_id).values_list('id', flat=True)
            )

        # 3. Estadísticas de ventas desde Order Service
        order_url = os.getenv('ORDER_SERVICE_URL', 'https://microservicio-4-order-service.onrender.com/api/orders')
        total_orders = 0
        total_units_sold = 0
        try:
            ids_param = ','.join(str(pid) for pid in product_ids)
            for attempt in range(3):
                try:
                    resp = requests.get(
                        f"{order_url}/seller_stats/",
                        params={'product_ids': ids_param},
                        timeout=15.0
                    )
                    if resp.status_code == 200:
                        stats = resp.json()
                        total_orders = stats.get('total_orders', 0)
                        total_units_sold = stats.get('total_units_sold', 0)
                        break
                    else:
                        print(f"Intento {attempt + 1}: seller_stats retornó {resp.status_code}")
                except requests.exceptions.Timeout:
                    print(f"Intento {attempt + 1}: timeout al llamar a seller_stats")
                    if attempt < 2:
                        import time
                        time.sleep(2)
                except Exception as e:
                    print(f"Intento {attempt + 1}: error al llamar a seller_stats: {e}")
                    break
        except Exception as e:
            print(f"No se pudo obtener estadísticas de ventas: {e}")

        return Response({
            'seller_id': int(seller_id),
            'seller_name': seller_name,
            'total_products': len(product_ids),
            'total_orders': total_orders,
            'total_units_sold': total_units_sold,
        })

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product']
    ordering_fields = ['created_at']
