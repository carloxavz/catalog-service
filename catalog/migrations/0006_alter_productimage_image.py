from django.db import migrations
import cloudinary.models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_add_product_categories_m2m'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productimage',
            name='image',
            field=cloudinary.models.CloudinaryField(max_length=255, verbose_name='image'),
        ),
    ]
