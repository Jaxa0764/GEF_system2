#!/bin/sh
set -e

# Auto-create admin if ADMIN_USERNAME and ADMIN_PASSWORD are set
if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "Checking for admin user..."
    python manage.py create-admin --username "$ADMIN_USERNAME" 2>&1 || echo "Admin already exists or creation skipped."
fi

# Start the server
exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
