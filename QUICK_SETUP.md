# Quick Setup Guide - Start Here!

Follow these steps in order to get your pipeline running.

## Step 1: Check Prerequisites

```bash
# Check if gcloud is installed
gcloud --version

# Check if Python 3.8+ is installed
python3 --version

# Check if pip is installed
pip3 --version
```

**If any are missing:**
- Install gcloud: https://cloud.google.com/sdk/docs/install
- Install Python: https://www.python.org/downloads/

---

## Step 2: GCP Authentication & Project Setup

```bash
# 1. Login to GCP
gcloud auth login

# 2. List your projects to find your project ID
gcloud projects list

# 3. Set your project (replace with your actual project ID)
export GCP_PROJECT_ID="your-actual-project-id"
gcloud config set project $GCP_PROJECT_ID

# 4. Enable Application Default Credentials (needed for Python scripts)
gcloud auth application-default login

# 5. Get your project number (you'll need this later)
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")
echo "Your project number is: $GCP_PROJECT_NUMBER"
```

---

## Step 3: Enable Required APIs

```bash
# Enable all three required APIs at once
gcloud services enable \
  storagetransfer.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  --project=$GCP_PROJECT_ID

# Verify they're enabled (should see 3 results)
gcloud services list --enabled --project=$GCP_PROJECT_ID | grep -E "(storagetransfer|storage|bigquery)"
```

---

## Step 4: Create GCS Bucket

```bash
# Choose a unique bucket name (must be globally unique)
# Suggestion: use your project ID as part of the name
export GCS_BUCKET="nasa-power-${GCP_PROJECT_ID}"

# Create the bucket
gsutil mb -p $GCP_PROJECT_ID -c STANDARD -l us-central1 gs://$GCS_BUCKET/

# Create directory structure
gsutil -m mkdir gs://$GCS_BUCKET/manifests/
gsutil -m mkdir gs://$GCS_BUCKET/power_ard_mirror/
gsutil -m mkdir gs://$GCS_BUCKET/processed/

# Verify bucket exists
gsutil ls gs://$GCS_BUCKET/
```

**Expected output:** You should see the three directories listed.

---

## Step 5: Grant Storage Transfer Service Permissions

**CRITICAL:** This step is required for the data transfer to work!

```bash
# Grant permissions to the Storage Transfer Service agent
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectViewer gs://$GCS_BUCKET

gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://$GCS_BUCKET

# Verify permissions were granted
gsutil iam get gs://$GCS_BUCKET | grep storage-transfer-service
```

**Expected output:** You should see the STS service account listed.

---

## Step 6: Install Python Dependencies

```bash
cd /Users/kyle/Desktop/pixel-planet-101

# (Optional but recommended) Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Verify imports work
python -c "import google.cloud.storage; import boto3; import xarray; import gcsfs; print('✅ All imports successful')"
```

---

## Step 7: Configure Environment Variables

**Option A: Set environment variables for the session (recommended for testing)**

```bash
# Add these to your current shell session
export GCP_PROJECT_ID="your-actual-project-id"
export GCP_PROJECT_NUMBER="your-project-number"
export GCS_BUCKET="nasa-power-your-project-id"
export GCP_REGION="us-central1"

# Verify variables are set
echo "Project: $GCP_PROJECT_ID"
echo "Bucket: $GCS_BUCKET"
echo "Project Number: $GCP_PROJECT_NUMBER"
```

**Option B: Create a .env file (recommended for permanent setup)**

```bash
# Create .env file (never commit this to git!)
cat > .env << EOF
GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_PROJECT_NUMBER=${GCP_PROJECT_NUMBER}
GCS_BUCKET=${GCS_BUCKET}
GCP_REGION=us-central1
EOF

# Source it before running scripts
source .env
```

**Option C: Edit config.py directly (not recommended)**

If you prefer, you can edit `src/pixel_planet/config.py` and replace the default values.

---

## Step 8: Verify Setup

Run this verification script:

```bash
python3 << 'EOF'
import os
from pixel_planet.config import PROJECT_ID, DEST_BUCKET, PROJECT_NUMBER, BQ_DATASET

print("=" * 50)
print("Configuration Verification")
print("=" * 50)
print(f"✓ Project ID: {PROJECT_ID}")
print(f"✓ Project Number: {PROJECT_NUMBER}")
print(f"✓ GCS Bucket: {DEST_BUCKET}")
print(f"✓ BigQuery Dataset: {BQ_DATASET}")
print("=" * 50)

# Check for placeholder values
issues = []
if PROJECT_ID == "your-gcp-project":
    issues.append("❌ PROJECT_ID is still placeholder - set GCP_PROJECT_ID env var")
if PROJECT_NUMBER == "YOUR_PROJECT_NUMBER":
    issues.append("❌ PROJECT_NUMBER is still placeholder - set GCP_PROJECT_NUMBER env var")
if DEST_BUCKET == "your-gcs-bucket":
    issues.append("❌ DEST_BUCKET is still placeholder - set GCS_BUCKET env var")

if issues:
    print("\n⚠️  Issues found:")
    for issue in issues:
        print(f"  {issue}")
    print("\nPlease set the environment variables and try again.")
else:
    print("\n✅ All configuration looks good!")
    print("\nYou're ready to run the pipeline!")
    print("\nNext step: python src/pixel_planet/run_pipeline.py")
EOF
```

---

## Step 9: Run the Pipeline

### Option A: Run full pipeline (45-90 minutes)

```bash
python src/pixel_planet/run_pipeline.py
```

### Option B: Run step-by-step (recommended for first run)

```bash
# Step 1: Build manifest (2-5 min)
python src/pixel_planet/build_manifest.py

# Step 2: Transfer data (10-30 min) - SLOW, get coffee!
python src/pixel_planet/run_sts_transfer.py

# Step 3: Convert to Parquet (2-5 min)
python src/pixel_planet/zarr_to_parquet.py

# Step 4: Load to BigQuery (30 sec)
python src/pixel_planet/load_to_bigquery.py

# Step 5: Train ML model (5-15 min)
python src/pixel_planet/train_bqml_model.py
```

---

## Quick Setup Cheatsheet

**Copy-paste this entire block (replace YOUR_PROJECT_ID):**

```bash
# Set your project ID
export GCP_PROJECT_ID="YOUR_PROJECT_ID"

# Login and configure
gcloud auth login
gcloud auth application-default login
gcloud config set project $GCP_PROJECT_ID

# Get project number
export GCP_PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --format="value(projectNumber)")

# Enable APIs
gcloud services enable storagetransfer.googleapis.com storage.googleapis.com bigquery.googleapis.com --project=$GCP_PROJECT_ID

# Create bucket
export GCS_BUCKET="nasa-power-${GCP_PROJECT_ID}"
gsutil mb -p $GCP_PROJECT_ID -c STANDARD -l us-central1 gs://$GCS_BUCKET/
gsutil -m mkdir gs://$GCS_BUCKET/manifests/ gs://$GCS_BUCKET/power_ard_mirror/ gs://$GCS_BUCKET/processed/

# Grant STS permissions
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectViewer gs://$GCS_BUCKET
gsutil iam ch serviceAccount:project-${GCP_PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://$GCS_BUCKET

# Install Python deps
cd /Users/kyle/Desktop/pixel-planet-101
pip install -r requirements.txt

# Verify setup
python -c "from pixel_planet.config import PROJECT_ID, DEST_BUCKET; print(f'Project: {PROJECT_ID}, Bucket: {DEST_BUCKET}')"

# Run pipeline
python src/pixel_planet/run_pipeline.py
```

---

## Troubleshooting

### "Command not found: gcloud"
Install the gcloud CLI: https://cloud.google.com/sdk/docs/install

### "Permission denied" errors
Run: `gcloud auth application-default login`

### "Bucket name already exists"
Choose a different bucket name: `export GCS_BUCKET="nasa-power-myuniquename"`

### "API not enabled"
Re-run: `gcloud services enable storagetransfer.googleapis.com storage.googleapis.com bigquery.googleapis.com`

### Python import errors
Reinstall: `pip install --upgrade -r requirements.txt`

---

## Cost Warning ⚠️

Running the full pipeline will incur GCP costs:
- **First run:** $10-20
- **Monthly:** $15-30

**Set up billing alerts:**
```bash
# Open billing in browser
gcloud alpha billing budgets list
```

Or go to: https://console.cloud.google.com/billing/budgets

---

## Next Steps After Setup

Once the pipeline runs successfully:
1. Query your forecasts in BigQuery Console
2. Explore the data in `YOUR_PROJECT.weather.davao_precip_2025`
3. Customize the Area of Interest (AOI) for your location
4. Run the data quality tests: `python tests/test_data_quality.py`

---

**Need more help?** See:
- `CHECKLIST.md` - Detailed checklist
- `docs/SETUP_GUIDE.md` - Comprehensive setup guide
- `docs/RUNBOOK.md` - Operations manual

