# apps/catalog/migrations/0003_install_trigram.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        # Make sure this matches your last migration file name in apps/catalog/migrations/
        ('catalog', '0002_banner_flashsale'), 
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql="DROP EXTENSION IF EXISTS pg_trgm;"
        ),
    ]