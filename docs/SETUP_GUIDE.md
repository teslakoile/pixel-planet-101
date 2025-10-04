# Setup Guide: NASA POWER → GCP Pipeline

## Before You Begin

This guide will help you set up the NASA POWER to BigQuery ML pipeline from scratch. You'll need:

- A Google Cloud Platform account
- `gcloud` CLI installed and configured
- Python 3.8+ installed
- Basic knowledge of command line operations

---

## Step 1: Configure GCP Project

### 1.1 Set Project Variables

First, determine your configuration values:

```bash
# Set your GCP project ID
export GCP_PROJECT_ID="your-project-id-here"

# Get your project number
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")

# Set your preferred region
export GCP_REGION="us-central1"

# Choose a unique bucket name
export GCS_BUCKET="nasa-power-${GCP_PROJECT_ID}"

echo "Project ID: $GCP_PROJECT_ID"
echo "Project Number: $GCP_PROJECT_NUMBER"
echo "Bucket Name: $GCS_BUCKET"
```

### 1.2 Update Configuration File

Edit `src/pixel_planet/config.py` and update the default values, or set environment variables:

```bash
# Set environment variables (recommended)
export GCP_PROJECT_ID="your-project-id"
export GCP_PROJECT_NUMBER="your-project-number"
export GCS_BUCKET="your-bucket-name"
```

---

## Step 2: Enable Required APIs

```bash
# Enable Storage Transfer Service API
gcloud services enable storagetransfer.googleapis.com --project=$GCP_PROJECT_ID

# Enable Cloud Storage API
gcloud services enable storage.googleapis.com --project=$GCP_PROJECT_ID

# Enable BigQuery API
gcloud services enable bigquery.googleapis.com --project=$GCP_PROJECT_ID
```

**Verify APIs are enabled:**
```bash
gcloud services list --enabled --filter="NAME:(storagetransfer.googleapis.com OR storage.googleapis.com OR bigquery.googleapis.com)" --project=$GCP_PROJECT_ID
```

---

## Step 3: Set Up Authentication

### Option A: Development (Application Default Credentials)

```bash
gcloud auth application-default login
gcloud config set project $GCP_PROJECT_ID
```

**Verify authentication:**
```bash
gcloud auth application-default print-access-token
```

### Option B: Production (Service Account)

```bash
# Create service account
gcloud iam service-accounts create nasa-power-pipeline \
    --display-name="NASA POWER Pipeline Service Account" \
    --project=$GCP_PROJECT_ID

# Grant necessary roles
for ROLE in roles/storage.admin roles/bigquery.admin roles/storagetransfer.admin; do
  gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:nasa-power-pipeline@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
    --role="$ROLE"
done

# Download key
gcloud iam service-accounts keys create ~/nasa-power-key.json \
    --iam-account=nasa-power-pipeline@${GCP_PROJECT_ID}.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=~/nasa-power-key.json
```

---

## Step 4: Create GCS Bucket

```bash
# Create bucket
gsutil mb -p $GCP_PROJECT_ID -c STANDARD -l $GCP_REGION gs://$GCS_BUCKET/

# Create directory structure
gsutil -m mkdir gs://$GCS_BUCKET/manifests/
gsutil -m mkdir gs://$GCS_BUCKET/power_ard_mirror/
gsutil -m mkdir gs://$GCS_BUCKET/processed/

# Verify bucket creation
gsutil ls gs://$GCS_BUCKET/
```

---

## Step 5: Grant STS Service Agent Permissions

**Critical:** Storage Transfer Service uses a special service account that needs permissions.

```bash
# Grant permissions to STS service agent
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectViewer gs://$GCS_BUCKET
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://$GCS_BUCKET

# Verify permissions
gsutil iam get gs://$GCS_BUCKET
```

---

## Step 6: Install Python Dependencies

```bash
cd /Users/kyle/Desktop/pixel-planet-101

# Install requirements
pip install -r requirements.txt

# Verify installations
python -c "import google.cloud.storage; import boto3; import xarray; import gcsfs; print('✓ All imports successful')"
```

---

## Step 7: Verify Setup

Run this verification script:

```bash
python -c "
from pixel_planet.config import PROJECT_ID, DEST_BUCKET, BQ_DATASET
print(f'Project ID: {PROJECT_ID}')
print(f'Bucket: {DEST_BUCKET}')
print(f'BQ Dataset: {BQ_DATASET}')
print('✓ Configuration loaded successfully')
"
```

---

## Step 8: Run the Pipeline

### Test with Step 1 Only

Start by testing just the manifest generation:

```bash
python src/pixel_planet/build_manifest.py
```

If successful, you should see:
```
✓ Step 1 Complete: TSV manifest created successfully
```

### Run Full Pipeline

Once Step 1 works, run the complete pipeline:

```bash
python src/pixel_planet/run_pipeline.py
```

**Estimated time:** 45-90 minutes (first run)

---

## Troubleshooting Setup

### Issue: "Permission denied" errors

**Solution:** Ensure you've run `gcloud auth application-default login` or set `GOOGLE_APPLICATION_CREDENTIALS`

### Issue: "Bucket not found"

**Solution:** Verify bucket name in config matches the bucket you created:
```bash
gsutil ls | grep nasa-power
```

### Issue: "API not enabled"

**Solution:** Re-run the API enablement commands:
```bash
gcloud services enable storagetransfer.googleapis.com storage.googleapis.com bigquery.googleapis.com --project=$GCP_PROJECT_ID
```

### Issue: Python import errors

**Solution:** Reinstall requirements in a clean environment:
```bash
pip install --upgrade -r requirements.txt
```

---

## Next Steps

After successful setup:

1. **Review the architecture:** Read `docs/ARCHITECTURE.md`
2. **Learn operations:** Study `docs/RUNBOOK.md`
3. **Customize for your use case:** Edit AOI coordinates in `config.py`
4. **Run data quality tests:** Execute `tests/test_data_quality.py`

---

## Cost Estimation

Before running the full pipeline, be aware of estimated costs:

- **First full run:** $10-20
- **Monthly (with updates):** $15-30
- **Storage only:** $2-5/month

Set up billing alerts in GCP Console to monitor costs.

---

## Getting Help

- **Implementation Plan:** See `context_engineering/IMPLEMENTATION_PLAN_NASA_POWER_GCP_PIPELINE.md`
- **NASA POWER Docs:** https://power.larc.nasa.gov/docs/
- **GCP Support:** https://cloud.google.com/support

