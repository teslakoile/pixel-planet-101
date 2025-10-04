#!/bin/bash
# Train all 6 DNN models for weather forecasting

set -e  # Exit on error

echo "🚀 Training all 6 DNN weather forecasting models..."
echo "   Each model takes ~10-30 minutes"
echo ""

MODELS=("precipitation" "temperature" "wind" "humidity" "solar_radiation" "cloud_cover")

for model in "${MODELS[@]}"; do
    echo ""
    echo "========================================"
    echo "Training: $model"
    echo "========================================"
    python -m pixel_planet.train_bqml_model --target "$model"
    
    if [ $? -eq 0 ]; then
        echo "✓ $model model trained successfully"
    else
        echo "✗ Failed to train $model model"
        exit 1
    fi
done

echo ""
echo "========================================"
echo "✅ All 6 models trained successfully!"
echo "========================================"
echo ""
echo "Next step: Generate forecasts with:"
echo "  ./forecast_all_parameters.sh"

