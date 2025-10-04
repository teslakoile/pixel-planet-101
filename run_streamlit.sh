#!/bin/bash

# Script to run the Streamlit app locally

set -e

echo "🌍 Starting Pixel Planet Streamlit App..."
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null
then
    echo "❌ Streamlit not found. Installing dependencies..."
    pip install streamlit plotly
fi

echo "🚀 Launching Streamlit app..."
echo ""
echo "   The app will open in your browser at http://localhost:8501"
echo "   Press Ctrl+C to stop the server"
echo ""

# Run streamlit
streamlit run streamlit_app.py

