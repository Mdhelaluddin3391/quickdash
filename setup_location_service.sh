#!/bin/bash
# Location Service Feature Setup Guide
# Quick setup script for the location-based service availability feature

set -e

echo "================================"
echo "Location Service Feature Setup"
echo "================================"
echo ""

# Step 1: Database Migration
echo "Step 1: Creating database migrations..."
python manage.py makemigrations warehouse
echo "✓ Migrations created"
echo ""

# Step 2: Apply migrations
echo "Step 2: Applying migrations to database..."
python manage.py migrate warehouse
echo "✓ Migrations applied"
echo ""

# Step 3: Create admin
echo "Step 3: Creating superuser for admin access..."
echo "You'll be prompted to create a superuser if one doesn't exist"
python manage.py create_admin 2>/dev/null || echo "✓ Admin already exists or using existing"
echo ""

# Step 4: Information
echo "================================"
echo "Setup Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Go to Django Admin:"
echo "   http://localhost:8000/admin/warehouse/servicearea/"
echo ""
echo "2. Create service areas for your warehouses:"
echo "   - Select warehouse"
echo "   - Enter zone name (e.g., 'North Zone', 'Downtown')"
echo "   - Set center point (latitude/longitude)"
echo "   - Set radius in kilometers"
echo "   - Set estimated delivery time in minutes"
echo ""
echo "3. Test the HTML page:"
echo "   http://localhost:8000/accounts/location/service-check/"
echo ""
echo "4. Test API endpoints:"
echo "   curl 'http://localhost:8000/api/v1/wms/location/check-service/?latitude=40.7128&longitude=-74.0060'"
echo ""
echo "5. Integrate into your frontend:"
echo "   - Use /api/v1/wms/location/check-service/ endpoint"
echo "   - Show service area info when customer saves address"
echo "   - Display 'Service not available' message with nearest service area"
echo ""
echo "For detailed documentation, see: LOCATION_SERVICE_FEATURE.md"
echo ""
