#!/bin/bash
###############################################################################
# Deploy Pixel Planet Weather Agent API to Google Cloud Run
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-pixel-planet-101}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="pixel-planet-api"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying Pixel Planet API to Cloud Run${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${YELLOW}Not logged in to gcloud. Logging in...${NC}"
    gcloud auth login
fi

# Set project
echo -e "${YELLOW}Setting GCP project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "${YELLOW}Enabling required APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    containerregistry.googleapis.com \
    cloudbuild.googleapis.com \
    bigquery.googleapis.com \
    aiplatform.googleapis.com

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME} .

# Get environment variables from .env if available
if [ -f .env ]; then
    echo -e "${YELLOW}Loading environment variables from .env...${NC}"
    source .env
fi

BQ_DATASET="${BQ_DATASET:-weather}"
BQ_TABLE="${BQ_TABLE:-forecast_results}"
VERTEX_AI_MODEL="${VERTEX_AI_MODEL:-gemini-2.0-flash-exp}"

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},BQ_DATASET=${BQ_DATASET},BQ_TABLE=${BQ_TABLE},VERTEX_AI_MODEL=${VERTEX_AI_MODEL}" \
    --port 8080

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Service URL: ${GREEN}${SERVICE_URL}${NC}"
echo ""
echo "API Endpoints:"
echo "  - Health Check: ${SERVICE_URL}/health"
echo "  - API Docs: ${SERVICE_URL}/docs"
echo "  - Activity Assessment: ${SERVICE_URL}/api/v1/assess-activity"
echo "  - Forecast Data: ${SERVICE_URL}/api/v1/forecast-data"
echo ""
echo "Test the API:"
echo "  curl ${SERVICE_URL}/health"
echo ""

