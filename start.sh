#!/bin/bash

# Read configuration from config.json
CONFIG_FILE="config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file not found at $CONFIG_FILE"
    exit 1
fi

# Helper to read JSON value
get_config() {
    python3 -c "import json, sys; print(json.load(open('$CONFIG_FILE'))['$1'])" 2>/dev/null
}

API_UI_PORT=$(get_config "testerPort")
API_SERVER_PORT=$(get_config "serverPort")

# Defaults if config fails
API_UI_PORT=${API_UI_PORT:-8010}
API_SERVER_PORT=${API_SERVER_PORT:-8011}

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    
    # Kill all background jobs started by this script
    kill $(jobs -p) 2>/dev/null
    
    echo "🧹 Cleaning up ports..."
    # Try to use npx to kill ports, suppressing output
    npx kill-port $API_UI_PORT $API_SERVER_PORT >/dev/null 2>&1
    
    echo "✅ Done. All services stopped."
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

echo "🚀 Initializing API Tester System..."
echo "Configuration loaded:"
echo "  API UI Port:       $API_UI_PORT"
echo "  API Server Port:   $API_SERVER_PORT"

# Start API Tester (UI + Python Server)
echo "---------------------------------------------------"
echo "🧪 Starting API Tester..."
cd frontend && npm start > ../api_tester.log 2>&1 &
API_TESTER_PID=$!
echo "   -> API Tester running in background (logs in api_tester.log)"

echo "---------------------------------------------------"
echo "🎉 All services are up and running!"
echo ""
echo "👉 API Tester UI:       http://localhost:$API_UI_PORT"
echo ""
echo "Press Ctrl+C to stop everything."

# Wait for any process to exit
wait

