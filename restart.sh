#!/bin/bash

# Kill existing server
echo "Stopping existing server..."
pkill -f "python.*main.py" || pkill -f "uvicorn.*main:app" || true
sleep 2

# Start server
echo "Starting server..."
cd /Users/rayandabbagh/Desktop/gate-project/backend
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -q -r requirements.txt
python3 main.py 8000

