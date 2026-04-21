#!/bin/bash

echo "🚀 Starting MPS Support Chatbot..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build containers
echo "📦 Building containers..."
docker-compose build

# Start services
echo "🎬 Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
docker-compose ps

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📍 Access your services:"
echo "   - Backend API:  http://localhost:8000"
echo "   - Admin Panel:  http://localhost:3000"
echo "   - Chat Widget:  http://localhost:5173"
echo "   - API Docs:     http://localhost:8000/docs"
echo ""
echo "📋 Useful commands:"
echo "   - View logs:    docker-compose logs -f"
echo "   - Stop all:     docker-compose down"
echo "   - Restart:      docker-compose restart"
echo ""
