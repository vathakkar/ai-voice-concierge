#!/bin/bash
# =============================================================================
# AI Voice Concierge - Log Retrieval Script
# =============================================================================
#
# This script downloads and displays recent application logs from Azure App Service.
# It's useful for debugging issues, monitoring performance, and reviewing call logs.
#
# Usage: ./get_recent_logs.sh
#
# Prerequisites:
# - Azure CLI installed and authenticated
# - Access to the Azure App Service
# - Proper permissions to download logs
#
# Features:
# - Downloads complete log archive from Azure App Service
# - Extracts and finds the most recent Docker log
# - Displays the last 100 lines for quick review
# - Handles missing log files gracefully
#
# Security Notes:
# - Logs may contain sensitive information - handle with care
# - Downloaded logs are stored locally in ./logs/ directory
# - Consider cleaning up log files after debugging
# =============================================================================

# Azure resource configuration
# Update these values to match your Azure App Service setup
RESOURCE_GROUP="ai-concierge"
APP_NAME="ai-voice-concierge"

echo "Downloading logs from Azure App Service..."
echo "Resource Group: $RESOURCE_GROUP"
echo "App Name: $APP_NAME"
echo ""

# Download logs from Azure App Service
# This creates a logs.zip file containing all application logs
az webapp log download --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --log-file logs.zip

# Extract the downloaded logs
# -o flag overwrites existing files
# Redirect output to /dev/null to suppress verbose extraction messages
echo "Extracting logs..."
unzip -o logs.zip -d logs > /dev/null

# Find the most recent Docker log file
# ls -t sorts by modification time (newest first)
# head -n 1 gets the first (most recent) file
echo "Finding most recent Docker log..."
LOG_FILE=$(ls -t logs/LogFiles/*docker.log | head -n 1)

# Check if log file exists and display recent entries
if [ -f "$LOG_FILE" ]; then
    echo "Showing last 100 lines of $LOG_FILE:"
    echo "============================================================================="
    tail -100 "$LOG_FILE"
    echo "============================================================================="
    echo ""
    echo "Log file: $LOG_FILE"
    echo "Total lines in log: $(wc -l < "$LOG_FILE")"
else
    echo "No Docker log file found in logs/LogFiles/"
    echo "Available files:"
    ls -la logs/LogFiles/ 2>/dev/null || echo "No LogFiles directory found"
fi

echo ""
echo "Log retrieval complete."
echo "Note: Log files are stored in ./logs/ directory"
echo "Consider cleaning up log files after debugging: rm -rf logs/ logs.zip" 