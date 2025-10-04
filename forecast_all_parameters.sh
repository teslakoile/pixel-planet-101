#!/bin/bash
# Generate 2-week forecasts for all 6 weather parameters

set -e  # Exit on error

echo "📈 Generating batch forecasts for all 6 parameters..."
echo "   Horizon: 336 hours (14 days)"
echo ""

MODELS=("precipitation" "temperature" "wind" "humidity" "solar_radiation" "cloud_cover")

for model in "${MODELS[@]}"; do
    echo ""
    echo "========================================"
    echo "Forecasting: $model"
    echo "========================================"
    python -m pixel_planet.batch_forecast --model "$model"
    
    if [ $? -eq 0 ]; then
        echo "✓ $model forecast generated successfully"
    else
        echo "✗ Failed to generate $model forecast"
        exit 1
    fi
done

echo ""
echo "========================================"
echo "✅ All 6 forecasts generated successfully!"
echo "========================================"
echo ""
echo "Forecast tables created in BigQuery:"
for model in "${MODELS[@]}"; do
    echo "  • weather.${model}_forecast"
done

