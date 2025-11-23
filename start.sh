#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Read configuration from config.json
CONFIG_FILE="config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file not found at $CONFIG_FILE"
    exit 1
fi

# Setup virtual environment
VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Install/update requirements
if [ -f "requirements.txt" ]; then
    echo "📥 Installing/updating Python dependencies..."
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
fi

# Helper to read JSON value (using venv python)
get_config() {
    python -c "import json, sys; c=json.load(open('$CONFIG_FILE')); print(c.get('$1', ''))" 2>/dev/null
}

get_nested_config() {
    python -c "import json, sys; c=json.load(open('$CONFIG_FILE')); print(c.get('$1', {}).get('$2', ''))" 2>/dev/null
}

API_SERVER_HOST=$(get_nested_config "app" "host")
API_SERVER_PORT=$(get_nested_config "app" "port")

# Defaults if config fails
API_SERVER_HOST=${API_SERVER_HOST:-0.0.0.0}
API_SERVER_PORT=${API_SERVER_PORT:-3020}

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping all services..."
    
    # Kill all background jobs started by this script
    kill $(jobs -p) 2>/dev/null
    
    echo "🧹 Cleaning up ports..."
    # Kill processes on the server port
    lsof -ti:$API_SERVER_PORT | xargs kill -9 2>/dev/null || true
    
    # Deactivate virtual environment
    deactivate 2>/dev/null
    
    echo "✅ Done. All services stopped."
}

# Trap SIGINT (Ctrl+C) and call cleanup
trap cleanup SIGINT

echo "🚀 Initializing API Tester System..."
echo "Configuration loaded:"
echo "  Server Host:       $API_SERVER_HOST"
echo "  Server Port:       $API_SERVER_PORT"

# Generate endpoints if configured
if python -c "import json; c=json.load(open('$CONFIG_FILE')); exit(0 if c.get('autoGenerateEndpoints', False) else 1)" 2>/dev/null; then
    echo "---------------------------------------------------"
    echo "📝 Generating endpoints..."
    python -m src.generator.endpoints
fi

# Start Python Server (serves both API and UI)
echo "---------------------------------------------------"
echo "🧪 Starting API Tester Server..."
python -m src.server.wrapper > api_tester.log 2>&1 &
API_SERVER_PID=$!
echo "   -> Server running in background (logs in api_tester.log)"
echo "   -> PID: $API_SERVER_PID"

# Wait a moment for server to start
sleep 3

echo "---------------------------------------------------"
echo "🎉 Server is up and running!"
echo ""
echo "👉 API Tester UI:       http://localhost:$API_SERVER_PORT"
echo "👉 API Documentation:   http://localhost:$API_SERVER_PORT/docs"
echo ""
echo "Press Ctrl+C to stop the server."

# Wait for the server process
wait $API_SERVER_PID

