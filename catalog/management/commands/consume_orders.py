import pika
import json
import os
import sys
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from catalog.models import Product

class Command(BaseCommand):
    help = 'Consume order events from RabbitMQ and update stock accordingly'

    def handle(self, *args, **options):
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.stdout.write(self.style.SUCCESS(f'Starting RabbitMQ consumer on {rabbitmq_host}...'))

        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='order_queue', durable=True)

            def callback(ch, method, properties, body):
                # Ensure a fresh DB connection for each message in long-running processes
                close_old_connections()
                try:
                    data = json.loads(body)
                    event = data.get('event')
                    items = data.get('items', [])
                    
                    self.stdout.write(f"Received event: {event} for order {data.get('order_id')}")

                    for item in items:
                        try:
                            product = Product.objects.get(id=item['product_id'])
                            quantity = item['quantity']
                            
                            if event == 'order_created':
                                product.stock = max(0, product.stock - quantity)
                                product.save()
                                self.stdout.write(self.style.SUCCESS(f"Reduced {quantity} stock from product {product.id}. New stock: {product.stock}"))
                            elif event == 'order_cancelled':
                                product.stock += quantity
                                product.save()
                                self.stdout.write(self.style.SUCCESS(f"Restored {quantity} stock to product {product.id}. New stock: {product.stock}"))
                        except Product.DoesNotExist:
                            self.stdout.write(self.style.ERROR(f"Product {item['product_id']} not found"))
                            
                    # Acknowledge message after processing successfully
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing message: {str(e)}"))
                    # If error, do not ack so it can be retried or put to dead letter queue
                    # (To avoid infinite loop if bad message, you can also nack or ack depending on policy)

            # Set prefetch count to 1 for fair dispatch
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue='order_queue', on_message_callback=callback)

            self.stdout.write(self.style.SUCCESS('Waiting for messages. To exit press CTRL+C'))
            channel.start_consuming()
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('Stopping consumer...'))
            try:
                sys.exit(0)
            except SystemExit:
                os._exit(0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Connection failed: {e}'))
