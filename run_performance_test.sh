#!/bin/bash

echo "🚀 Running AI Voice Concierge Performance Test"
echo "=============================================="

# Load environment variables more robustly
echo "📋 Loading environment variables..."

# Source the .env file directly to avoid xargs quote issues
if [ -f .env ]; then
    # Use source to load .env file, handling quotes properly
    set -a  # automatically export all variables
    source .env
    set +a  # stop auto-exporting
    echo "✅ .env file loaded successfully"
else
    echo "❌ .env file not found"
    exit 1
fi

# Check required variables
if [ -z "$BASE_URL" ]; then
    echo "❌ BASE_URL not found in .env file"
    echo "Current environment variables:"
    env | grep -E "(BASE_URL|TWILIO)" || echo "No relevant variables found"
    exit 1
fi

if [ -z "$TWILIO_AUTH_TOKEN" ]; then
    echo "❌ TWILIO_AUTH_TOKEN not found in .env file"
    exit 1
fi

echo "✅ Environment loaded:"
echo "   BASE_URL: $BASE_URL"
echo "   TWILIO_AUTH_TOKEN: ${TWILIO_AUTH_TOKEN:0:8}..."
echo "   TEST_CALLER_ID: ${TEST_CALLER_ID:-'Not set'}"
echo "   TEST_SPEECH: ${TEST_SPEECH:0:50}..."
echo ""

# Run the performance test
echo "🧪 Starting performance test..."
python3 performance_test.py

echo ""
echo "✅ Performance test completed!" 