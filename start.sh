#!/bin/bash

# Gate - Startup Script

echo "Starting Gate - AI Agent Team"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.8+"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    echo ""
fi

# Check if port 8000 is in use and kill it
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "WARNING: Port 8000 is already in use. Stopping existing process..."
    kill -9 $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
fi

PORT=${1:-8000}

echo "Starting backend server..."
echo "   API will be available at http://localhost:$PORT"
echo "   Open frontend/index.html in your browser to use the UI"
echo ""
echo "   Press Ctrl+C to stop"
echo ""

cd backend
python3 main.py $PORT

