 #!/bin/bash
###############################################################################
# Test the deployed Pixel Planet API
###############################################################################

# Get service URL from Cloud Run
PROJECT_ID="${GCP_PROJECT_ID:-pixel-planet-101}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="pixel-planet-api"

SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)' 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Service not found. Using localhost for testing..."
    SERVICE_URL="http://localhost:8080"
fi

echo "🧪 Testing Pixel Planet API"
echo "Service URL: $SERVICE_URL"
echo ""

# Test 1: Health check
echo "1️⃣ Testing health endpoint..."
curl -s "${SERVICE_URL}/health" | jq '.'
echo ""

# Test 2: Activity assessment
echo "2️⃣ Testing activity assessment..."
curl -s -X POST "${SERVICE_URL}/api/v1/assess-activity" \
    -H "Content-Type: application/json" \
    -d '{
      "location_name": "Mt. Apo",
      "latitude": 6.987,
      "longitude": 125.273,
      "start_time": "2025-10-04T05:00:00",
      "end_time": "2025-10-05T21:00:00",
      "activity_type": "hiking"
    }' | jq '.assessment, .chart_data.location'
echo ""

# Test 3: Forecast data
echo "3️⃣ Testing forecast data endpoint..."
curl -s -X POST "${SERVICE_URL}/api/v1/forecast-data" \
    -H "Content-Type: application/json" \
    -d '{
      "location_name": "Davao City",
      "latitude": 7.07,
      "longitude": 125.61,
      "start_time": "2025-10-04T00:00:00",
      "end_time": "2025-10-04T12:00:00"
    }' | jq '.success, .total_records, .location'
echo ""

echo "✅ API tests complete!"
