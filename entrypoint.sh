#!/bin/bash
set -e

echo "🚀 Starting eidosSpeech v2..."

# Run database migrations
echo "📦 Running database migrations..."
python run_migrations.py

# Start the application
echo "✓ Migrations complete, starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001 --proxy-headers
