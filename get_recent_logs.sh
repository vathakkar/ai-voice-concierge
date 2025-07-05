#!/bin/bash
# Usage: ./get_recent_logs.sh
# Downloads and prints the last 100 lines of the most recent docker log for ai-voice-concierge

RESOURCE_GROUP="ai-concierge"
APP_NAME="ai-voice-concierge"

# Download logs
az webapp log download --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --log-file logs.zip
unzip -o logs.zip -d logs > /dev/null

# Find the most recent docker log
LOG_FILE=$(ls -t logs/LogFiles/*docker.log | head -n 1)

if [ -f "$LOG_FILE" ]; then
    echo "Showing last 100 lines of $LOG_FILE:"
    tail -100 "$LOG_FILE"
else
    echo "No docker log file found."
fi 