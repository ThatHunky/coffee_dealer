#!/bin/bash

# Coffee Dealer Bot Setup Script

set -e

echo "☕ Coffee Dealer Bot - Setup Script"
echo "===================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.12"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then 
    echo "❌ Python $required_version or higher is required. Found: $python_version"
    exit 1
fi
echo "✅ Python $python_version found"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "⚠️  Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
    echo "✅ .env file created - PLEASE EDIT IT WITH YOUR CREDENTIALS!"
    echo ""
    echo "You need to add:"
    echo "  - Telegram bot token from @BotFather"
    echo "  - Google Gemini API key from https://aistudio.google.com/app/apikey"
    echo "  - Your Telegram user ID from @userinfobot"
else
    echo "⚠️  .env file already exists"
fi
echo ""

# Run tests
echo "Running tests..."
if pytest tests/ -v; then
    echo "✅ All tests passed"
else
    echo "⚠️  Some tests failed (this is OK if you haven't configured API keys yet)"
fi
echo ""

echo "===================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your credentials"
echo "  2. Run: python -m src.main"
echo ""
echo "Happy scheduling! ☕"
