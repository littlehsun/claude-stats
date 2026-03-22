#!/bin/bash
cd "$(dirname "$0")"

# Kill any existing instance on port 5050
kill $(lsof -ti:5050) 2>/dev/null

# Activate venv if it exists
if [ -f venv/bin/activate ]; then
  source venv/bin/activate
fi

echo "Starting Claude Stats at http://localhost:5050"
python3 app.py
