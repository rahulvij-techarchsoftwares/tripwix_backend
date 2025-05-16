#!/bin/bash
set -e

# Define database credentials
DB_NAME=${POSTGRES_DB:-tripwix_db}
DB_USER=${POSTGRES_USER:-postgres}
DB_PASSWORD=${POSTGRES_PASSWORD:-MS0KOj8PLkBVqxtwtrcI}
DB_HOST=${DB_HOST:-tripwixdb.cp577dcvhmm6.eu-west-1.rds.amazonaws.com}

# Define S3 bucket and directory
S3_BUCKET="tripwix-platform"
S3_UPLOADS_DIR="uploads"

# Drop all tables from the database
echo "Dropping all tables from database $DB_NAME..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Clean uploads directory on S3
#echo "Cleaning uploads directory on S3..."
#python manage.py clean_s3_uploads $S3_BUCKET $S3_UPLOADS_DIR

# Run migrations
echo "Running migrations..."
python manage.py migrate

# Load data fixtures
echo "Loading data fixtures..."
python manage.py loaddata apps/properties/fixtures/countries.json
python manage.py loaddata apps/properties/fixtures/details.json
python manage.py loaddata tripwix_backend/fixtures/cms.json

# migrate data
echo "Migrating data..."
echo "Owners..."
python manage.py import_owners
echo "Managers..."
python manage.py import_managers
echo "Properties..."
python manage.py import_properties
echo "Amenities..."
python manage.py import_amenities
echo "Rates..."
python manage.py import_rates
echo "Rooms..."
python manage.py import_rooms
echo "Bathrooms..."
python manage.py import_bathrooms
echo "CMS..."
python manage.py import_cms
echo "..."


# Create superuser
#echo "Creating superuser..."
#python manage.py create_test_superuser

echo "Database reset, uploads cleaned, and data loaded successfully."