# Pipeline Setup & Execution Checklist

Use this checklist to track your progress through the setup and execution phases.

## Phase 0: Prerequisites & Environment Setup

### 0.1 Configuration
- [ ] Determine GCP project ID
- [ ] Get GCP project number: `gcloud projects describe PROJECT_ID --format="value(projectNumber)"`
- [ ] Choose GCP region (default: `us-central1`)
- [ ] Choose unique GCS bucket name
- [ ] Update `src/pixel_planet/config.py` or set environment variables

### 0.2 Enable GCP APIs
- [ ] Enable Storage Transfer Service API
- [ ] Enable Cloud Storage API
- [ ] Enable BigQuery API
- [ ] Verify all APIs enabled: `gcloud services list --enabled`

### 0.3 Authentication
- [ ] Set up Application Default Credentials: `gcloud auth application-default login`
- [ ] Set project: `gcloud config set project PROJECT_ID`
- [ ] Verify authentication: `gcloud auth application-default print-access-token`

### 0.4 Storage Transfer Service Permissions
- [ ] Grant `roles/storage.objectViewer` to STS service agent
- [ ] Grant `roles/storage.objectAdmin` to STS service agent
- [ ] Verify permissions: `gsutil iam get gs://BUCKET_NAME`

### 0.5 Python Dependencies
- [ ] Create/activate virtual environment (recommended)
- [ ] Install requirements: `pip install -r requirements.txt`
- [ ] Verify imports: `python -c "import google.cloud.storage; import boto3; import xarray; import gcsfs"`

### 0.6 GCS Bucket Creation
- [ ] Create GCS bucket: `gsutil mb -p PROJECT_ID -c STANDARD -l REGION gs://BUCKET_NAME/`
- [ ] Create `manifests/` directory
- [ ] Create `power_ard_mirror/` directory
- [ ] Create `processed/` directory
- [ ] Verify structure: `gsutil ls gs://BUCKET_NAME/`

---

## Phase 1: Build TSV URL Manifest

- [ ] Run `python src/pixel_planet/build_manifest.py`
- [ ] Verify manifest exists: `gsutil ls gs://BUCKET/manifests/`
- [ ] Check first line is `TsvHttpData-1.0`: `gsutil cat gs://BUCKET/manifests/power_zarr.tsv | head -1`
- [ ] Verify URL count: `gsutil cat gs://BUCKET/manifests/power_zarr.tsv | wc -l`

**Expected:** 1000+ URLs, sorted, starting with header

---

## Phase 2: Storage Transfer Service (S3 → GCS)

- [ ] Run `python src/pixel_planet/run_sts_transfer.py`
- [ ] Monitor job status (script polls automatically)
- [ ] Wait for completion (10-30 minutes)
- [ ] Verify Zarr objects transferred: `gsutil ls gs://BUCKET/power_ard_mirror/...zarr/ | head -20`
- [ ] Check metadata files exist: `gsutil cat gs://BUCKET/power_ard_mirror/.../zarr/.zattrs`

**Expected:** All Zarr objects in GCS, matching source count

---

## Phase 3: Zarr → Parquet Conversion

- [ ] Run `python src/pixel_planet/zarr_to_parquet.py`
- [ ] Wait for completion (2-5 minutes)
- [ ] Verify Parquet file exists: `gsutil ls -lh gs://BUCKET/processed/`
- [ ] Check file size is reasonable (>1 MB)

**Expected:** Single Parquet file in `processed/` directory

---

## Phase 4: Load Parquet → BigQuery

- [ ] Run `python src/pixel_planet/load_to_bigquery.py`
- [ ] Wait for load job completion (10-30 seconds)
- [ ] Verify table exists: `bq ls --project_id=PROJECT --dataset_id=weather`
- [ ] Check row count: `bq query --use_legacy_sql=false "SELECT COUNT(*) FROM \`PROJECT.weather.davao_precip_2025\`"`
- [ ] Preview data in BigQuery Console

**Expected:** Table with timestamp and precipitation columns

---

## Phase 5: Train BigQuery ML Model

- [ ] Run `python src/pixel_planet/train_bqml_model.py`
- [ ] Wait for training completion (5-15 minutes)
- [ ] Review evaluation metrics
- [ ] Check forecast preview output
- [ ] Verify model exists: `bq ls --project_id=PROJECT --dataset_id=weather --models`

**Expected:** Trained ARIMA_PLUS model with reasonable metrics

---

## Phase 6: Validation & Testing

- [ ] Run data quality tests: `python tests/test_data_quality.py`
- [ ] Query forecast manually in BigQuery Console
- [ ] Export forecast to CSV for verification
- [ ] Check prediction intervals are reasonable (non-negative, proper bounds)

---

## Phase 7: Documentation & Handoff

- [ ] Review `docs/ARCHITECTURE.md`
- [ ] Read `docs/RUNBOOK.md`
- [ ] Bookmark GCP console pages (Storage Transfer, BigQuery)
- [ ] Set up billing alerts
- [ ] Document any customizations made

---

## Troubleshooting Reference

If you encounter issues:

1. **Permission Errors:** Verify STS service agent permissions
2. **Import Errors:** Reinstall requirements: `pip install --upgrade -r requirements.txt`
3. **Zarr Read Errors:** Ensure STS transfer completed successfully
4. **BQML Training Errors:** Check for sufficient historical data (2+ years)

See `docs/RUNBOOK.md` for detailed troubleshooting.

---

## Estimated Timeline

- **Setup (Phase 0):** 15-30 minutes
- **Phase 1:** 2-5 minutes
- **Phase 2:** 10-30 minutes (automated)
- **Phase 3:** 2-5 minutes
- **Phase 4:** 10-30 seconds
- **Phase 5:** 5-15 minutes (automated)

**Total first run:** 45-90 minutes

---

## Next Steps After Completion

- [ ] Customize AOI coordinates for your location
- [ ] Adjust time range as needed
- [ ] Schedule periodic updates (monthly/quarterly)
- [ ] Explore additional NASA POWER variables
- [ ] Scale to multiple locations
- [ ] Build visualization dashboard

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-04  
**Project:** Pixel Planet 101 - NASA Space Apps Challenge 2025

