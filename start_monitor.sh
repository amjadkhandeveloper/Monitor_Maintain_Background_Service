#!/bin/bash
echo "Starting Java JAR Service Monitor..."
echo ""
echo "Make sure you have installed the requirements:"
echo "  pip3 install -r requirements.txt"
echo ""
echo "Starting Flask server..."
echo "Access the dashboard at: http://localhost:5001"
echo "(You can specify a different port as an argument: ./start_monitor.sh 8080)"
echo ""
python3 app.py ${1:-5001}

