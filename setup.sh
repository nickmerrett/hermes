#!/bin/bash

# Hermes - Setup Script

set -e

echo "======================================"
echo "Hermes Setup"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✓ .env file created"
        echo ""
        echo "⚠️  IMPORTANT: Please edit .env and add your API keys:"
        echo "   - ANTHROPIC_API_KEY (required)"
        echo "   - NEWS_API_KEY (required)"
        echo ""
        read -p "Press Enter to continue after you've added your API keys..."
    else
        echo "❌ Error: .env.example not found"
        echo "   Please create .env manually with your API keys"
        exit 1
    fi
else
    echo "✓ .env file already exists"
fi

# Create data directories
echo ""
echo "Creating data directories..."
mkdir -p data/db data/chroma
chmod 755 data data/db data/chroma
echo "✓ Data directories created"

# Check if config/customers.yaml exists
echo ""
if [ ! -f config/customers.yaml ]; then
    echo "⚠️  Warning: config/customers.yaml not found"
    echo "   You can add customers via the web UI or create the file manually"
    echo "   See docs/CONFIGURATION.md for details"
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Start Hermes:"
echo "   docker-compose up -d"
echo ""
echo "2. Access the dashboard:"
echo "   http://localhost:3000"
echo ""
echo "3. Add your first customer:"
echo "   - Click '+ Add Customer' in the dashboard"
echo "   - Or manually edit config/customers.yaml"
echo ""
echo "4. API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "For detailed setup instructions, see docs/SETUP.md"
echo ""
