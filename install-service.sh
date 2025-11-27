#!/bin/bash
# Installation script for Coffee Dealer Bot systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="coffee-dealer-bot"
SERVICE_FILE="${SCRIPT_DIR}/${SERVICE_NAME}.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "📦 Installing Coffee Dealer Bot systemd service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service file not found: $SERVICE_FILE"
    exit 1
fi

# Update service file with current user and paths
CURRENT_USER=$(logname 2>/dev/null || echo "${SUDO_USER:-$USER}")
CURRENT_GROUP=$(id -gn "$CURRENT_USER")
PROJECT_DIR="$SCRIPT_DIR"

echo "📝 Configuring service for user: $CURRENT_USER"
echo "📁 Project directory: $PROJECT_DIR"

# Create a temporary service file with updated paths
TEMP_SERVICE=$(mktemp)
sed -e "s|User=thathunky|User=$CURRENT_USER|g" \
    -e "s|Group=thathunky|Group=$CURRENT_GROUP|g" \
    -e "s|/home/thathunky/coffee_dealer|$PROJECT_DIR|g" \
    "$SERVICE_FILE" > "$TEMP_SERVICE"

# Copy service file to systemd directory
echo "📋 Copying service file to $SYSTEMD_DIR..."
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/${SERVICE_NAME}.service"
rm "$TEMP_SERVICE"

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

echo "✅ Service installed successfully!"
echo ""
echo "⚠️  IMPORTANT: Make sure your .env file is configured in $PROJECT_DIR"
echo "   Required variables: BOT_TOKEN, GEMINI_API_KEY, ADMIN_IDS"
echo ""
echo "📚 Available commands:"
echo "  sudo systemctl start $SERVICE_NAME    - Start the bot"
echo "  sudo systemctl stop $SERVICE_NAME     - Stop the bot"
echo "  sudo systemctl restart $SERVICE_NAME  - Restart the bot"
echo "  sudo systemctl enable $SERVICE_NAME   - Enable autostart on boot"
echo "  sudo systemctl disable $SERVICE_NAME  - Disable autostart"
echo "  sudo systemctl status $SERVICE_NAME   - Check bot status"
echo "  sudo journalctl -u $SERVICE_NAME -f   - View bot logs (follow mode)"
echo ""

