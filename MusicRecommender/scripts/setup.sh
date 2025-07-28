#!/bin/bash

set -e

echo "🎵 Setting up Music Playlist Optimizer..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python 3.9+ is installed
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
required_version="3.9"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo -e "${RED}Error: Python 3.9 or higher is required. Found: $python_version${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python version check passed${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠️  Please update .env file with your API keys and configuration${NC}"
fi

# Create necessary directories
mkdir -p logs
mkdir -p data/models
mkdir -p data/cache

# Initialize database (if using local setup)
if [ "$1" != "--skip-db" ]; then
    echo "Setting up database..."
    python scripts/migrate.py
    
    echo "Seeding initial data..."
    python scripts/seed_data.py
fi

# Install pre-commit hooks if available
if command -v pre-commit &> /dev/null; then
    echo "Installing pre-commit hooks..."
    pre-commit install
fi

# Create systemd service file (optional)
if [ "$1" == "--systemd" ]; then
    echo "Creating systemd service file..."
    cat > music-playlist-optimizer.service << EOF
[Unit]
Description=Music Playlist Optimizer API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python -m src.api.main
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    
    echo -e "${GREEN}✓ Systemd service file created${NC}"
    echo "To install: sudo cp music-playlist-optimizer.service /etc/systemd/system/"
    echo "To enable: sudo systemctl enable music-playlist-optimizer"
    echo "To start: sudo systemctl start music-playlist-optimizer"
fi

echo -e "${GREEN}🎉 Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Update .env file with your API keys"
echo "2. Start the application:"
echo "   - Development: python -m src.api.main"
echo "   - Production: docker-compose up -d"
echo ""
echo "3. Access the API at http://localhost:8000"
echo "4. View API docs at http://localhost:8000/docs"
