#!/bin/bash
# NASA POWER Pipeline Setup Script
# This script helps you set up the pipeline step-by-step

set -e  # Exit on error

echo "=================================="
echo "NASA POWER Pipeline Setup"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "  $1"
}

# Check if gcloud is installed
echo "Checking prerequisites..."
if ! command -v gcloud &> /dev/null; then
    print_error "gcloud CLI not found"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
print_success "gcloud CLI found"

if ! command -v python3 &> /dev/null; then
    print_error "python3 not found"
    exit 1
fi
print_success "python3 found ($(python3 --version))"

echo ""
echo "=================================="
echo "Step 1: GCP Project Configuration"
echo "=================================="
echo ""

# Get project ID
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "Available GCP projects:"
    gcloud projects list --format="table(projectId,name)"
    echo ""
    read -p "Enter your GCP Project ID: " GCP_PROJECT_ID
fi

if [ -z "$GCP_PROJECT_ID" ]; then
    print_error "Project ID is required"
    exit 1
fi

export GCP_PROJECT_ID
print_success "Project ID set to: $GCP_PROJECT_ID"

# Set project
print_info "Setting active project..."
gcloud config set project $GCP_PROJECT_ID

# Get project number
print_info "Retrieving project number..."
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")
if [ -z "$GCP_PROJECT_NUMBER" ]; then
    print_error "Failed to get project number"
    exit 1
fi
print_success "Project number: $GCP_PROJECT_NUMBER"

echo ""
echo "=================================="
echo "Step 2: Authentication"
echo "=================================="
echo ""

# Check if already authenticated
if gcloud auth application-default print-access-token &> /dev/null; then
    print_success "Already authenticated"
else
    print_info "Opening browser for authentication..."
    gcloud auth application-default login
    print_success "Authentication complete"
fi

echo ""
echo "=================================="
echo "Step 3: Enable APIs"
echo "=================================="
echo ""

print_info "Enabling required APIs (this may take 1-2 minutes)..."
gcloud services enable \
  storagetransfer.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  --project=$GCP_PROJECT_ID

print_success "APIs enabled"

# Verify
enabled=$(gcloud services list --enabled --project=$GCP_PROJECT_ID --filter="NAME:(storagetransfer.googleapis.com OR storage.googleapis.com OR bigquery.googleapis.com)" --format="value(NAME)" | wc -l)
if [ "$enabled" -eq 3 ]; then
    print_success "All 3 APIs verified"
else
    print_warning "Expected 3 APIs, found $enabled"
fi

echo ""
echo "=================================="
echo "Step 4: GCS Bucket Setup"
echo "=================================="
echo ""

# Choose bucket name
if [ -z "$GCS_BUCKET" ]; then
    default_bucket="nasa-power-${GCP_PROJECT_ID}"
    read -p "Enter GCS bucket name [$default_bucket]: " GCS_BUCKET
    GCS_BUCKET=${GCS_BUCKET:-$default_bucket}
fi

export GCS_BUCKET
print_info "Bucket name: $GCS_BUCKET"

# Check if bucket exists
if gsutil ls -b gs://$GCS_BUCKET &> /dev/null; then
    print_warning "Bucket already exists: gs://$GCS_BUCKET"
    read -p "Use existing bucket? (y/n): " use_existing
    if [ "$use_existing" != "y" ]; then
        print_error "Please choose a different bucket name and run again"
        exit 1
    fi
else
    print_info "Creating bucket..."
    gsutil mb -p $GCP_PROJECT_ID -c STANDARD -l us-central1 gs://$GCS_BUCKET/
    print_success "Bucket created"
fi

# Create directory structure
print_info "Creating directory structure..."
gsutil -m mkdir gs://$GCS_BUCKET/manifests/ 2>/dev/null || true
gsutil -m mkdir gs://$GCS_BUCKET/power_ard_mirror/ 2>/dev/null || true
gsutil -m mkdir gs://$GCS_BUCKET/processed/ 2>/dev/null || true
print_success "Directory structure ready"

echo ""
echo "=================================="
echo "Step 5: Storage Transfer Permissions"
echo "=================================="
echo ""

print_info "Granting permissions to Storage Transfer Service..."
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectViewer gs://$GCS_BUCKET
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://$GCS_BUCKET
print_success "STS permissions granted"

echo ""
echo "=================================="
echo "Step 6: Python Dependencies"
echo "=================================="
echo ""

print_info "Installing Python packages..."
pip install -q -r requirements.txt
print_success "Dependencies installed"

# Verify imports
print_info "Verifying imports..."
python3 -c "import google.cloud.storage; import boto3; import xarray; import gcsfs" 2>/dev/null
if [ $? -eq 0 ]; then
    print_success "All imports verified"
else
    print_error "Import verification failed"
    exit 1
fi

echo ""
echo "=================================="
echo "Step 7: Configuration"
echo "=================================="
echo ""

# Create .env file
print_info "Creating .env file..."
cat > .env << EOF
# GCP Configuration (generated by setup.sh)
export GCP_PROJECT_ID="${GCP_PROJECT_ID}"
export GCP_PROJECT_NUMBER="${GCP_PROJECT_NUMBER}"
export GCS_BUCKET="${GCS_BUCKET}"
export GCP_REGION="us-central1"
EOF

print_success "Configuration saved to .env"
print_info "Run 'source .env' to load these variables"

# Verify configuration
echo ""
print_info "Verifying configuration..."
source .env
python3 << 'EOF'
from pixel_planet.config import PROJECT_ID, DEST_BUCKET, PROJECT_NUMBER
import sys

issues = []
if PROJECT_ID == "your-gcp-project":
    issues.append("PROJECT_ID is still placeholder")
if PROJECT_NUMBER == "YOUR_PROJECT_NUMBER":
    issues.append("PROJECT_NUMBER is still placeholder")
if DEST_BUCKET == "your-gcs-bucket":
    issues.append("DEST_BUCKET is still placeholder")

if issues:
    print("\n⚠️  Configuration issues:")
    for issue in issues:
        print(f"  - {issue}")
    sys.exit(1)
else:
    print(f"✓ Project ID: {PROJECT_ID}")
    print(f"✓ Bucket: {DEST_BUCKET}")
    print(f"✓ Project Number: {PROJECT_NUMBER}")
EOF

if [ $? -eq 0 ]; then
    print_success "Configuration verified"
else
    print_error "Configuration verification failed"
    print_info "Make sure to run: source .env"
    exit 1
fi

echo ""
echo "=================================="
echo "✅ Setup Complete!"
echo "=================================="
echo ""
echo "Environment variables saved to: .env"
echo ""
echo "Before running the pipeline, execute:"
echo "  source .env"
echo ""
echo "Then run the pipeline:"
echo "  python src/pixel_planet/run_pipeline.py"
echo ""
echo "Or run step-by-step:"
echo "  python src/pixel_planet/build_manifest.py        # 2-5 min"
echo "  python src/pixel_planet/run_sts_transfer.py      # 10-30 min"
echo "  python src/pixel_planet/zarr_to_parquet.py       # 2-5 min"
echo "  python src/pixel_planet/load_to_bigquery.py      # 30 sec"
echo "  python src/pixel_planet/train_bqml_model.py      # 5-15 min"
echo ""
echo "⚠️  Estimated cost for first run: \$10-20"
echo ""
echo "Need help? Check:"
echo "  - QUICK_SETUP.md"
echo "  - docs/SETUP_GUIDE.md"
echo "  - docs/RUNBOOK.md"
echo ""

