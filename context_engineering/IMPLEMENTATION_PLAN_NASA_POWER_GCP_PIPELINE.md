# Implementation Plan: NASA POWER → GCP → BigQuery ML Pipeline

## Document Purpose

This document provides a **step-by-step implementation plan** for building an end-to-end data pipeline that:
1. Transfers NASA POWER Zarr data from AWS S3 to Google Cloud Storage (GCS)
2. Processes Zarr data into Parquet format
3. Loads data into BigQuery
4. Trains a BigQuery ML time-series forecast model with prediction intervals

**Target Audience:** AI agents and developers implementing the Pixel Planet 101 NASA Space Apps Challenge solution.

**Context Engineering Principles Applied:**
- ✓ Explicit prerequisites and validation steps
- ✓ Clear success criteria for each phase
- ✓ Configuration constants grouped and documented
- ✓ Error handling guidance
- ✓ Verification commands included
- ✓ Dependencies between steps clearly marked

---

## Architecture Overview

```markdown
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW PIPELINE                          │
└─────────────────────────────────────────────────────────────────────┘

Step 1: S3 Object Listing
┌──────────────────┐
│  NASA POWER S3   │
│  (Public Bucket) │──── boto3 (unsigned) ───> Generate TSV manifest
│  Zarr Store      │                            with HTTPS URLs
└──────────────────┘

Step 2: Storage Transfer Service (STS)
┌──────────────────┐
│  TSV Manifest    │──── GCS STS Job ────────> ┌──────────────────┐
│  (GCS Bucket)    │    (HTTP data source)      │  GCS Destination │
└──────────────────┘                            │  Zarr Mirror     │
                                                └──────────────────┘

Step 3: Zarr → Parquet Conversion
┌──────────────────┐
│  GCS Zarr Store  │──── xarray + fsspec ────> ┌──────────────────┐
│                  │     (subset AOI/time)      │  Parquet File    │
│                  │     → pandas → pyarrow     │  (GCS)           │
└──────────────────┘                            └──────────────────┘

Step 4: BigQuery Load
┌──────────────────┐
│  Parquet (GCS)   │──── BQ Load Job ─────────> ┌──────────────────┐
│                  │     (autodetect schema)     │  BigQuery Table  │
└──────────────────┘                            └──────────────────┘

Step 5: BigQuery ML Training
┌──────────────────┐
│  BigQuery Table  │──── CREATE MODEL ────────> ┌──────────────────┐
│  (time series)   │     ARIMA_PLUS              │  Trained Model   │
│                  │     ML.FORECAST             │  + Intervals     │
└──────────────────┘                            └──────────────────┘
```

---

## Phase 0: Prerequisites & Environment Setup

### 0.1 Required Information (TO BE CONFIGURED)

**Critical:** The following constants MUST be determined before beginning implementation:

```python
# ============================================================================
# CONFIGURATION CONSTANTS - FILL THESE VALUES BEFORE STARTING
# ============================================================================

# Google Cloud Project Settings
PROJECT_ID = "your-gcp-project-id"           # GCP project ID
PROJECT_NUMBER = "YOUR_PROJECT_NUMBER"       # Get from GCP Console Home
REGION = "us-central1"                       # Preferred GCP region

# GCS Bucket Settings
DEST_BUCKET = "your-gcs-bucket-name"         # GCS bucket for all pipeline data
                                             # Must be created before Step 1

# NASA POWER Zarr Configuration
# Browse available datasets: https://power.larc.nasa.gov/docs/services/api/
# Example daily precipitation: 'syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/'
ZARR_PREFIX = "syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/"
VAR_NAME = "PRECTOTCORR"                     # Variable name in Zarr store

# GCS Path Structure
MANIFEST_GCS_PATH = f"gs://{DEST_BUCKET}/manifests/power_zarr.tsv"
DEST_PREFIX = "power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/"
PARQUET_OUT = f"gs://{DEST_BUCKET}/processed/davao_precip_2025.parquet"

# Area of Interest (AOI) and Time Range
START_DATE = "2020-01-01"                    # ISO format: YYYY-MM-DD
END_DATE = "2025-12-31"
LAT_MIN, LAT_MAX = 7.0, 7.4                  # Davao City example
LON_MIN, LON_MAX = 125.2, 125.7

# BigQuery Settings
BQ_DATASET = "weather"                       # BigQuery dataset name
BQ_TABLE = "davao_precip_2025"              # BigQuery table name
BQ_MODEL = "rain_arima"                     # BQML model name

# AWS S3 Constants (NASA POWER public bucket)
S3_BUCKET = "nasa-power"
S3_REGION = "us-west-2"
```

**How to get PROJECT_NUMBER:**
```bash
gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)"
```

---

### 0.2 Enable Required GCP APIs

**Status Check Command:**
```bash
gcloud services list --enabled --project=YOUR_PROJECT_ID
```

**Enable APIs:**
```bash
# Storage Transfer Service API
gcloud services enable storagetransfer.googleapis.com --project=YOUR_PROJECT_ID

# Cloud Storage API
gcloud services enable storage.googleapis.com --project=YOUR_PROJECT_ID

# BigQuery API
gcloud services enable bigquery.googleapis.com --project=YOUR_PROJECT_ID
```

**Validation:**
```bash
# Verify all three APIs are enabled
gcloud services list --enabled --filter="NAME:(storagetransfer.googleapis.com OR storage.googleapis.com OR bigquery.googleapis.com)" --project=YOUR_PROJECT_ID
```

**Expected Output:** Three rows showing the enabled APIs.

---

### 0.3 Authentication Setup

**Option A: Development Machine (Application Default Credentials)**
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

**Option B: Service Account (Production)**
```bash
# Create service account
gcloud iam service-accounts create nasa-power-pipeline \
    --display-name="NASA POWER Pipeline Service Account" \
    --project=YOUR_PROJECT_ID

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:nasa-power-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:nasa-power-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:nasa-power-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storagetransfer.admin"

# Download key
gcloud iam service-accounts keys create ~/nasa-power-key.json \
    --iam-account=nasa-power-pipeline@YOUR_PROJECT_ID.iam.gserviceaccount.com

# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=~/nasa-power-key.json
```

**Validation:**
```bash
gcloud auth application-default print-access-token
```
**Expected Output:** Access token string (indicates authentication is working).

---

### 0.4 Grant STS Service Agent Permissions

**Critical:** Storage Transfer Service uses a special service account that needs permissions.

**Get STS Service Agent Email:**
```bash
# The format is: project-PROJECT_NUMBER@storage-transfer-service.iam.gserviceaccount.com
# Use PROJECT_NUMBER from Step 0.1
```

**Grant Permissions:**
```bash
# Permission to read TSV manifest from GCS
gsutil iam ch serviceAccount:project-PROJECT_NUMBER@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectViewer \
    gs://YOUR_BUCKET_NAME

# Permission to write to destination bucket
gsutil iam ch serviceAccount:project-PROJECT_NUMBER@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin \
    gs://YOUR_BUCKET_NAME
```

**Validation:**
```bash
gsutil iam get gs://YOUR_BUCKET_NAME
```
**Expected Output:** Service agent listed with appropriate roles.

**Reference:** [Storage Transfer Service access requirements](https://cloud.google.com/storage-transfer/docs/configure-access#http)

---

### 0.5 Install Python Dependencies

**Create requirements file:**
```txt
# Google Cloud SDKs
google-cloud-storage-transfer>=1.0.0
google-cloud-storage>=2.0.0
google-cloud-bigquery>=3.0.0

# AWS SDK (for public S3 access)
boto3>=1.26.0
botocore>=1.29.0

# Data Processing
xarray>=2023.1.0
zarr>=2.13.0
fsspec>=2023.1.0
gcsfs>=2023.1.0
pandas>=2.0.0
pyarrow>=12.0.0
numpy>=1.24.0

# Optional: Progress tracking
tqdm>=4.65.0
```

**Install:**
```bash
cd /Users/kyle/Desktop/pixel-planet-101
pip install -r requirements.txt
```

**Validation:**
```bash
python -c "import google.cloud.storage; import boto3; import xarray; import gcsfs; print('All imports successful')"
```

**Expected Output:** `All imports successful`

---

### 0.6 Create GCS Bucket

**Create bucket:**
```bash
gsutil mb -p YOUR_PROJECT_ID -c STANDARD -l us-central1 gs://YOUR_BUCKET_NAME/
```

**Create directory structure:**
```bash
gsutil -m mkdir gs://YOUR_BUCKET_NAME/manifests/
gsutil -m mkdir gs://YOUR_BUCKET_NAME/power_ard_mirror/
gsutil -m mkdir gs://YOUR_BUCKET_NAME/processed/
```

**Validation:**
```bash
gsutil ls gs://YOUR_BUCKET_NAME/
```
**Expected Output:** Three directories listed.

---

## Phase 1: Build TSV URL Manifest from S3

### 1.1 Objective

Generate a TSV file containing HTTPS URLs for all objects in the NASA POWER Zarr store on S3. This manifest will be used by Storage Transfer Service to copy data to GCS.

**Why URL list approach?**
- NASA POWER S3 bucket is public (no AWS credentials required)
- STS S3 source requires AWS keys; URL list avoids this
- Officially supported for public HTTP(S) data sources

---

### 1.2 Implementation

**File:** `src/pixel_planet/build_manifest.py`

```python
"""
Step 1: Build TSV manifest of NASA POWER Zarr store URLs
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import gcsfs
from typing import List

# ============================================================================
# CONFIGURATION (import from config.py in production)
# ============================================================================
PROJECT_ID = "your-gcp-project"
DEST_BUCKET = "your-gcs-bucket"
ZARR_PREFIX = "syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/"
MANIFEST_GCS_PATH = f"gs://{DEST_BUCKET}/manifests/power_zarr.tsv"

S3_BUCKET = "nasa-power"
S3_REGION = "us-west-2"

# ============================================================================
# FUNCTIONS
# ============================================================================

def list_s3_objects_public(bucket: str, prefix: str, region: str) -> List[str]:
    """
    List all objects in a public S3 bucket with unsigned requests.
    
    Args:
        bucket: S3 bucket name
        prefix: Object key prefix to filter
        region: AWS region
        
    Returns:
        List of object keys
    """
    # Configure unsigned S3 client (no credentials needed)
    s3_client = boto3.client(
        "s3",
        region_name=region,
        config=Config(signature_version=UNSIGNED)
    )
    
    object_keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    
    # Ensure prefix ends with /
    prefix_normalized = prefix.rstrip("/") + "/"
    
    print(f"Listing objects from s3://{bucket}/{prefix_normalized}")
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_normalized):
        if "Contents" not in page:
            continue
            
        for obj in page["Contents"]:
            object_keys.append(obj["Key"])
    
    print(f"Found {len(object_keys)} objects")
    return object_keys


def build_https_urls(bucket: str, keys: List[str], region: str) -> List[str]:
    """
    Convert S3 keys to HTTPS URLs.
    
    Args:
        bucket: S3 bucket name
        keys: List of S3 object keys
        region: AWS region
        
    Returns:
        List of HTTPS URLs
    """
    urls = []
    for key in keys:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
        urls.append(url)
    return urls


def write_tsv_manifest(urls: List[str], gcs_path: str) -> None:
    """
    Write URL list to TSV file in GCS.
    
    STS requires:
    - Header: "TsvHttpData-1.0"
    - URLs must be lexicographically sorted
    - One URL per line
    
    Args:
        urls: List of HTTPS URLs
        gcs_path: GCS path (gs://bucket/path/file.tsv)
    """
    # Sort URLs (required by STS)
    urls_sorted = sorted(urls)
    
    # Write to GCS
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "w") as f:
        # Write TSV header
        f.write("TsvHttpData-1.0\n")
        
        # Write URLs
        for url in urls_sorted:
            f.write(url + "\n")
    
    print(f"Wrote manifest to {gcs_path}")
    print(f"Total URLs: {len(urls_sorted)}")


def main():
    """Main execution function."""
    # Step 1: List S3 objects
    object_keys = list_s3_objects_public(S3_BUCKET, ZARR_PREFIX, S3_REGION)
    
    if len(object_keys) == 0:
        raise ValueError(f"No objects found at s3://{S3_BUCKET}/{ZARR_PREFIX}")
    
    # Step 2: Build HTTPS URLs
    urls = build_https_urls(S3_BUCKET, object_keys, S3_REGION)
    
    # Step 3: Write TSV manifest to GCS
    write_tsv_manifest(urls, MANIFEST_GCS_PATH)
    
    print("\n✓ Step 1 Complete: TSV manifest created successfully")
    print(f"  Manifest location: {MANIFEST_GCS_PATH}")
    print(f"  Object count: {len(urls)}")


if __name__ == "__main__":
    main()
```

---

### 1.3 Execution

```bash
cd /Users/kyle/Desktop/pixel-planet-101
python src/pixel_planet/build_manifest.py
```

---

### 1.4 Validation

**Check manifest exists:**
```bash
gsutil ls gs://YOUR_BUCKET_NAME/manifests/
```

**Inspect first 10 lines:**
```bash
gsutil cat gs://YOUR_BUCKET_NAME/manifests/power_zarr.tsv | head -10
```

**Expected Output:**
```
TsvHttpData-1.0
https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/.zattrs
https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/.zgroup
...
```

**Count URLs:**
```bash
gsutil cat gs://YOUR_BUCKET_NAME/manifests/power_zarr.tsv | wc -l
```

**Success Criteria:**
- ✓ Manifest file exists in GCS
- ✓ First line is `TsvHttpData-1.0`
- ✓ URLs are sorted lexicographically
- ✓ URL count matches expected Zarr object count (typically 1000+)

---

## Phase 2: Transfer S3 → GCS via Storage Transfer Service

### 2.1 Objective

Create and execute a Storage Transfer Service job that reads the TSV manifest and copies all Zarr objects from NASA POWER S3 (via HTTPS) to GCS.

**STS Advantages:**
- Managed service (no manual download/upload)
- Parallel transfers (faster than sequential)
- Automatic retry on failures
- No AWS credentials needed (URL list approach)

---

### 2.2 Implementation

**File:** `src/pixel_planet/run_sts_transfer.py`

```python
"""
Step 2: Run Storage Transfer Service job (URL list → GCS)
"""
from google.cloud import storage_transfer
from datetime import datetime
import time

# ============================================================================
# CONFIGURATION
# ============================================================================
PROJECT_ID = "your-gcp-project"
DEST_BUCKET = "your-gcs-bucket"
MANIFEST_GCS_PATH = "gs://your-gcs-bucket/manifests/power_zarr.tsv"
DEST_PREFIX = "power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/"

# ============================================================================
# FUNCTIONS
# ============================================================================

def create_sts_job(
    project_id: str,
    manifest_url: str,
    dest_bucket: str,
    dest_prefix: str
) -> str:
    """
    Create a Storage Transfer Service job using HTTP data source.
    
    Args:
        project_id: GCP project ID
        manifest_url: GCS path to TSV manifest
        dest_bucket: Destination GCS bucket name
        dest_prefix: Destination path prefix within bucket
        
    Returns:
        Job name (format: transferJobs/...)
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    # Get today's date for schedule
    now = datetime.utcnow()
    
    # Build transfer job configuration
    transfer_job_config = storage_transfer.TransferJob(
        project_id=project_id,
        description="NASA POWER Zarr (URL list) → GCS mirror",
        status=storage_transfer.TransferJob.Status.ENABLED,
        
        # One-time schedule (start_date == end_date)
        schedule=storage_transfer.Schedule(
            schedule_start_date={
                "year": now.year,
                "month": now.month,
                "day": now.day
            },
            schedule_end_date={
                "year": now.year,
                "month": now.month,
                "day": now.day
            }
        ),
        
        # Transfer specification
        transfer_spec=storage_transfer.TransferSpec(
            # HTTP data source (URL list)
            http_data_source=storage_transfer.HttpData(
                list_url=manifest_url  # TSV manifest in GCS
            ),
            
            # GCS destination
            gcs_data_sink=storage_transfer.GcsData(
                bucket_name=dest_bucket,
                path=dest_prefix
            )
        )
    )
    
    # Create job
    print("Creating Storage Transfer Service job...")
    request = storage_transfer.CreateTransferJobRequest(
        transfer_job=transfer_job_config
    )
    
    response = client.create_transfer_job(request=request)
    job_name = response.name
    
    print(f"✓ Created job: {job_name}")
    return job_name


def run_sts_job(project_id: str, job_name: str) -> None:
    """
    Trigger immediate execution of STS job.
    
    Args:
        project_id: GCP project ID
        job_name: Job name from create_sts_job()
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    print("Triggering job run...")
    request = storage_transfer.RunTransferJobRequest(
        project_id=project_id,
        job_name=job_name
    )
    
    client.run_transfer_job(request=request)
    print(f"✓ Triggered run for: {job_name}")


def wait_for_job_completion(project_id: str, job_name: str, timeout_seconds: int = 3600) -> None:
    """
    Poll job status until completion or timeout.
    
    Args:
        project_id: GCP project ID
        job_name: Job name
        timeout_seconds: Maximum wait time (default 1 hour)
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    print("\nMonitoring job status...")
    start_time = time.time()
    
    while True:
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            print(f"⚠ Timeout after {timeout_seconds} seconds")
            break
        
        # List operations for this job
        request = storage_transfer.ListTransferOperationsRequest(
            name="transferOperations",
            filter=f'{{"project_id": "{project_id}", "job_names": ["{job_name}"]}}'
        )
        
        operations = client.list_transfer_operations(request=request)
        
        # Check latest operation
        for op in operations:
            metadata = op.metadata
            
            if metadata:
                status = metadata.status
                print(f"Status: {status}, Transferred: {metadata.counters.bytes_copied_to_sink} bytes")
                
                if status == storage_transfer.TransferOperation.Status.SUCCESS:
                    print("\n✓ Transfer completed successfully!")
                    return
                    
                elif status == storage_transfer.TransferOperation.Status.FAILED:
                    print(f"\n✗ Transfer failed: {metadata.error_breakdowns}")
                    raise RuntimeError("STS job failed")
        
        # Wait before next check
        time.sleep(30)


def main():
    """Main execution function."""
    # Step 1: Create STS job
    job_name = create_sts_job(
        project_id=PROJECT_ID,
        manifest_url=MANIFEST_GCS_PATH,
        dest_bucket=DEST_BUCKET,
        dest_prefix=DEST_PREFIX
    )
    
    # Step 2: Trigger job run
    run_sts_job(PROJECT_ID, job_name)
    
    # Step 3: Wait for completion
    print("\nTransfer in progress (this may take 10-30 minutes)...")
    wait_for_job_completion(PROJECT_ID, job_name)
    
    print("\n✓ Step 2 Complete: Zarr store transferred to GCS")
    print(f"  Destination: gs://{DEST_BUCKET}/{DEST_PREFIX}")


if __name__ == "__main__":
    main()
```

---

### 2.3 Execution

```bash
python src/pixel_planet/run_sts_transfer.py
```

**Expected Duration:** 10-30 minutes (depends on Zarr size and network)

---

### 2.4 Validation

**Check transferred files:**
```bash
gsutil ls gs://YOUR_BUCKET_NAME/power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/ | head -20
```

**Count objects:**
```bash
gsutil ls -r gs://YOUR_BUCKET_NAME/power_ard_mirror/**/*.* | wc -l
```

**Expected Output:** Object count should match manifest URL count (minus 1 for header).

**Check Zarr metadata files:**
```bash
gsutil cat gs://YOUR_BUCKET_NAME/power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/.zattrs
gsutil cat gs://YOUR_BUCKET_NAME/power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/.zgroup
```

**Success Criteria:**
- ✓ All Zarr objects transferred to GCS
- ✓ `.zattrs`, `.zgroup`, and `.zarray` metadata files exist
- ✓ Object count matches source
- ✓ No STS errors in console

---

## Phase 3: Zarr → Parquet Conversion with AOI Subsetting

### 3.1 Objective

Read the Zarr store from GCS, subset to the specified area of interest (AOI) and time range, aggregate spatially, and write a tidy Parquet file suitable for BigQuery.

**Transformations:**
1. Open Zarr with xarray
2. Subset by latitude/longitude bounds
3. Subset by time range
4. Aggregate spatially (mean across grid cells)
5. Convert to pandas DataFrame (tidy format)
6. Write Parquet to GCS

---

### 3.2 Implementation

**File:** `src/pixel_planet/zarr_to_parquet.py`

```python
"""
Step 3: Read Zarr from GCS, subset, and write Parquet
"""
import fsspec
import xarray as xr
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gcsfs
from typing import Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================
DEST_BUCKET = "your-gcs-bucket"
DEST_PREFIX = "power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/"
VAR_NAME = "PRECTOTCORR"

START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
LAT_MIN, LAT_MAX = 7.0, 7.4  # Davao City
LON_MIN, LON_MAX = 125.2, 125.7

ZARR_GCS_URL = f"gs://{DEST_BUCKET}/{DEST_PREFIX.rstrip('/')}"
PARQUET_OUT = f"gs://{DEST_BUCKET}/processed/davao_precip_2025.parquet"

# ============================================================================
# FUNCTIONS
# ============================================================================

def open_zarr_from_gcs(zarr_url: str) -> xr.Dataset:
    """
    Open Zarr store from GCS using fsspec mapper.
    
    Args:
        zarr_url: GCS URL (gs://bucket/path/store.zarr)
        
    Returns:
        xarray Dataset
    """
    print(f"Opening Zarr store: {zarr_url}")
    
    # Create fsspec mapper (gcsfs handles gs:// URLs)
    store = fsspec.get_mapper(zarr_url)
    
    # Open with xarray (consolidated=True for faster metadata access)
    ds = xr.open_zarr(store, consolidated=True)
    
    print(f"✓ Opened Zarr store")
    print(f"  Variables: {list(ds.data_vars)}")
    print(f"  Dimensions: {dict(ds.dims)}")
    print(f"  Coordinates: {list(ds.coords)}")
    
    return ds


def subset_data(
    ds: xr.Dataset,
    var_name: str,
    time_range: Tuple[str, str],
    lat_range: Tuple[float, float],
    lon_range: Tuple[float, float]
) -> xr.DataArray:
    """
    Subset dataset by variable, time, and spatial bounds.
    
    Args:
        ds: xarray Dataset
        var_name: Variable name to extract
        time_range: (start_date, end_date) as ISO strings
        lat_range: (lat_min, lat_max)
        lon_range: (lon_min, lon_max)
        
    Returns:
        xarray DataArray (subsetted)
    """
    print(f"\nSubsetting variable: {var_name}")
    print(f"  Time: {time_range[0]} to {time_range[1]}")
    print(f"  Latitude: {lat_range[0]} to {lat_range[1]}")
    print(f"  Longitude: {lon_range[0]} to {lon_range[1]}")
    
    # Extract variable
    da = ds[var_name]
    
    # Subset time
    da_sub = da.sel(time=slice(time_range[0], time_range[1]))
    
    # Subset lat/lon
    da_sub = da_sub.sel(
        lat=slice(lat_range[0], lat_range[1]),
        lon=slice(lon_range[0], lon_range[1])
    )
    
    # Load into memory (triggers actual data read from GCS)
    print("Loading data into memory...")
    da_sub = da_sub.load()
    
    print(f"✓ Subset complete")
    print(f"  Shape: {da_sub.shape}")
    print(f"  Size: {da_sub.nbytes / 1024 / 1024:.2f} MB")
    
    return da_sub


def aggregate_to_timeseries(da: xr.DataArray, var_name: str) -> pd.DataFrame:
    """
    Aggregate spatial dimensions (mean over lat/lon) to create time series.
    
    Args:
        da: xarray DataArray with dimensions (time, lat, lon)
        var_name: Variable name for column naming
        
    Returns:
        pandas DataFrame with columns [ts, {var_name}_mm]
    """
    print("\nAggregating spatial data (mean over grid cells)...")
    
    # Convert to DataFrame (long format)
    df = da.to_dataframe(name=f"{var_name}_mm").reset_index()
    
    # Group by time and take spatial mean
    df_agg = (
        df.groupby("time", as_index=False)[f"{var_name}_mm"]
        .mean()
        .rename(columns={"time": "ts"})
    )
    
    print(f"✓ Aggregation complete")
    print(f"  Rows: {len(df_agg)}")
    print(f"  Columns: {list(df_agg.columns)}")
    print(f"  Date range: {df_agg['ts'].min()} to {df_agg['ts'].max()}")
    
    return df_agg


def write_parquet_to_gcs(df: pd.DataFrame, gcs_path: str) -> None:
    """
    Write pandas DataFrame to Parquet file in GCS.
    
    Args:
        df: pandas DataFrame
        gcs_path: GCS destination path (gs://bucket/path/file.parquet)
    """
    print(f"\nWriting Parquet to: {gcs_path}")
    
    # Convert to PyArrow Table
    table = pa.Table.from_pandas(df)
    
    # Write to GCS
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")
    
    print(f"✓ Parquet file written")
    print(f"  Rows: {len(df)}")
    print(f"  Compression: snappy")


def main():
    """Main execution function."""
    # Step 1: Open Zarr from GCS
    ds = open_zarr_from_gcs(ZARR_GCS_URL)
    
    # Step 2: Subset data
    da_subset = subset_data(
        ds=ds,
        var_name=VAR_NAME,
        time_range=(START_DATE, END_DATE),
        lat_range=(LAT_MIN, LAT_MAX),
        lon_range=(LON_MIN, LON_MAX)
    )
    
    # Step 3: Aggregate to time series
    df = aggregate_to_timeseries(da_subset, VAR_NAME)
    
    # Step 4: Write Parquet
    write_parquet_to_gcs(df, PARQUET_OUT)
    
    print("\n✓ Step 3 Complete: Parquet file created")
    print(f"  Location: {PARQUET_OUT}")
    print(f"  Schema: ts (TIMESTAMP), {VAR_NAME}_mm (FLOAT64)")


if __name__ == "__main__":
    main()
```

---

### 3.3 Execution

```bash
python src/pixel_planet/zarr_to_parquet.py
```

**Expected Duration:** 2-5 minutes (depends on subset size)

---

### 3.4 Validation

**Check Parquet file exists:**
```bash
gsutil ls -lh gs://YOUR_BUCKET_NAME/processed/
```

**Inspect schema with pyarrow:**
```python
import pyarrow.parquet as pq
import gcsfs

fs = gcsfs.GCSFileSystem()
with fs.open("gs://YOUR_BUCKET_NAME/processed/davao_precip_2025.parquet", "rb") as f:
    parquet_file = pq.ParquetFile(f)
    print(parquet_file.schema)
    print(f"Num rows: {parquet_file.metadata.num_rows}")
```

**Expected Output:**
```
ts: timestamp[us, tz=UTC]
PRECTOTCORR_mm: double
Num rows: XXXX
```

**Success Criteria:**
- ✓ Parquet file exists in GCS
- ✓ Schema includes `ts` (TIMESTAMP) and precipitation column (FLOAT64)
- ✓ Row count matches expected time range
- ✓ No null/missing values in critical columns

---

## Phase 4: Load Parquet → BigQuery

### 4.1 Objective

Load the Parquet file from GCS into a BigQuery table with automatic schema detection.

**BigQuery Advantages:**
- Native Parquet support (no conversion needed)
- Auto-detect schema from Parquet metadata
- Columnar storage optimized for analytics
- Foundation for BQML training

---

### 4.2 Implementation

**File:** `src/pixel_planet/load_to_bigquery.py`

```python
"""
Step 4: Load Parquet from GCS to BigQuery table
"""
from google.cloud import bigquery
import time

# ============================================================================
# CONFIGURATION
# ============================================================================
PROJECT_ID = "your-gcp-project"
DEST_BUCKET = "your-gcs-bucket"
PARQUET_OUT = f"gs://{DEST_BUCKET}/processed/davao_precip_2025.parquet"

BQ_DATASET = "weather"
BQ_TABLE = "davao_precip_2025"
BQ_LOCATION = "US"  # or "EU", "us-central1", etc.

# ============================================================================
# FUNCTIONS
# ============================================================================

def create_dataset_if_not_exists(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    location: str
) -> None:
    """
    Create BigQuery dataset if it doesn't exist.
    
    Args:
        client: BigQuery client
        project_id: GCP project ID
        dataset_id: Dataset name
        location: BigQuery location (US, EU, etc.)
    """
    dataset_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    dataset_ref.location = location
    
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"✓ Dataset {dataset_id} ready")
    except Exception as e:
        print(f"Error creating dataset: {e}")
        raise


def load_parquet_to_bq(
    client: bigquery.Client,
    source_uri: str,
    table_id: str
) -> bigquery.LoadJob:
    """
    Load Parquet file from GCS to BigQuery table.
    
    Args:
        client: BigQuery client
        source_uri: GCS URI (gs://bucket/path/file.parquet)
        table_id: Fully-qualified table ID (project.dataset.table)
        
    Returns:
        Completed LoadJob
    """
    print(f"Loading {source_uri} → {table_id}")
    
    # Configure load job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        # Parquet has embedded schema, autodetect uses it
        autodetect=True,
        # Overwrite table if exists
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    # Start load job
    load_job = client.load_table_from_uri(
        source_uri,
        table_id,
        job_config=job_config
    )
    
    print(f"Job started: {load_job.job_id}")
    
    # Wait for completion
    print("Waiting for job to complete...")
    load_job.result()  # Blocks until done
    
    print(f"✓ Load job complete")
    return load_job


def validate_table(client: bigquery.Client, table_id: str) -> None:
    """
    Print table metadata for validation.
    
    Args:
        client: BigQuery client
        table_id: Fully-qualified table ID
    """
    table = client.get_table(table_id)
    
    print(f"\n✓ Table: {table_id}")
    print(f"  Rows: {table.num_rows:,}")
    print(f"  Size: {table.num_bytes / 1024 / 1024:.2f} MB")
    print(f"  Created: {table.created}")
    print(f"  Modified: {table.modified}")
    
    print(f"\n  Schema:")
    for field in table.schema:
        print(f"    - {field.name}: {field.field_type} (mode: {field.mode})")


def preview_data(client: bigquery.Client, table_id: str, limit: int = 5) -> None:
    """
    Query and print sample rows.
    
    Args:
        client: BigQuery client
        table_id: Fully-qualified table ID
        limit: Number of rows to preview
    """
    query = f"""
    SELECT *
    FROM `{table_id}`
    ORDER BY ts
    LIMIT {limit}
    """
    
    print(f"\n  Preview (first {limit} rows):")
    results = client.query(query).result()
    
    for row in results:
        print(f"    {dict(row)}")


def main():
    """Main execution function."""
    # Initialize BigQuery client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Ensure dataset exists
    create_dataset_if_not_exists(client, PROJECT_ID, BQ_DATASET, BQ_LOCATION)
    
    # Step 2: Load Parquet to BigQuery
    table_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    load_job = load_parquet_to_bq(client, PARQUET_OUT, table_id)
    
    # Step 3: Validate table
    validate_table(client, table_id)
    
    # Step 4: Preview data
    preview_data(client, table_id, limit=5)
    
    print("\n✓ Step 4 Complete: Data loaded to BigQuery")
    print(f"  Table: {table_id}")


if __name__ == "__main__":
    main()
```

---

### 4.3 Execution

```bash
python src/pixel_planet/load_to_bigquery.py
```

**Expected Duration:** 10-30 seconds

---

### 4.4 Validation

**Query table in BigQuery Console:**
```sql
SELECT 
  COUNT(*) as total_rows,
  MIN(ts) as earliest_date,
  MAX(ts) as latest_date,
  AVG(PRECTOTCORR_mm) as avg_precip_mm,
  MAX(PRECTOTCORR_mm) as max_precip_mm
FROM `YOUR_PROJECT.weather.davao_precip_2025`
```

**Via bq CLI:**
```bash
bq query --use_legacy_sql=false \
"SELECT COUNT(*) FROM \`YOUR_PROJECT.weather.davao_precip_2025\`"
```

**Success Criteria:**
- ✓ Table exists in BigQuery
- ✓ Row count matches Parquet file
- ✓ Schema matches expected (ts, PRECTOTCORR_mm)
- ✓ Date range is correct
- ✓ No null values in key columns

---

## Phase 5: Train BigQuery ML Time-Series Model

### 5.1 Objective

Train an ARIMA_PLUS time-series forecasting model in BigQuery ML that:
- Uses historical precipitation data
- Generates forecasts with prediction intervals (uncertainty bounds)
- Can be queried via SQL for 168-hour (7-day) forecasts

**BQML ARIMA_PLUS Features:**
- Automatic seasonality detection
- Handles missing values
- Generates confidence intervals (upper/lower bounds)
- Native SQL interface

---

### 5.2 Implementation

**File:** `src/pixel_planet/train_bqml_model.py`

```python
"""
Step 5: Train BigQuery ML ARIMA_PLUS model
"""
from google.cloud import bigquery
import time

# ============================================================================
# CONFIGURATION
# ============================================================================
PROJECT_ID = "your-gcp-project"
BQ_DATASET = "weather"
BQ_TABLE = "davao_precip_2025"
BQ_MODEL = "rain_arima"

HORIZON = 168  # Hours to forecast (7 days = 168 hours)
CONFIDENCE_LEVEL = 0.90  # 90% prediction intervals

# ============================================================================
# FUNCTIONS
# ============================================================================

def create_arima_model(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    model_id: str,
    table_id: str,
    horizon: int
) -> bigquery.QueryJob:
    """
    Create ARIMA_PLUS model for time-series forecasting.
    
    Args:
        client: BigQuery client
        project_id: GCP project ID
        dataset_id: Dataset name
        model_id: Model name
        table_id: Source table (project.dataset.table)
        horizon: Forecast horizon (number of time steps)
        
    Returns:
        Completed query job
    """
    model_full_id = f"{project_id}.{dataset_id}.{model_id}"
    
    print(f"Creating model: {model_full_id}")
    print(f"  Horizon: {horizon} time steps")
    
    # BQML CREATE MODEL SQL
    create_model_sql = f"""
    CREATE OR REPLACE MODEL `{model_full_id}`
    OPTIONS(
      MODEL_TYPE = 'ARIMA_PLUS',
      TIME_SERIES_TIMESTAMP_COL = 'ts',
      TIME_SERIES_DATA_COL = 'PRECTOTCORR_mm',
      HORIZON = {horizon},
      AUTO_ARIMA = TRUE,
      DATA_FREQUENCY = 'AUTO_FREQUENCY'
    ) AS
    SELECT 
      ts,
      PRECTOTCORR_mm
    FROM `{table_id}`
    WHERE ts >= '2020-01-01'  -- Training data start
    ORDER BY ts
    """
    
    print("Training model (this may take 5-15 minutes)...")
    query_job = client.query(create_model_sql)
    
    # Wait for completion
    query_job.result()
    
    print(f"✓ Model trained successfully")
    return query_job


def evaluate_model(
    client: bigquery.Client,
    model_id: str
) -> None:
    """
    Evaluate model training metrics.
    
    Args:
        client: BigQuery client
        model_id: Fully-qualified model ID (project.dataset.model)
    """
    evaluate_sql = f"""
    SELECT *
    FROM ML.EVALUATE(MODEL `{model_id}`)
    """
    
    print("\n  Model Evaluation Metrics:")
    results = client.query(evaluate_sql).result()
    
    for row in results:
        metrics = dict(row)
        for key, value in metrics.items():
            print(f"    {key}: {value}")


def generate_forecast(
    client: bigquery.Client,
    model_id: str,
    horizon: int,
    confidence_level: float,
    limit: int = 10
) -> None:
    """
    Generate and display forecast with prediction intervals.
    
    Args:
        client: BigQuery client
        model_id: Fully-qualified model ID
        horizon: Forecast horizon
        confidence_level: Confidence level for intervals (0.0-1.0)
        limit: Number of forecast rows to display
    """
    forecast_sql = f"""
    SELECT
      forecast_timestamp,
      forecast_value,
      prediction_interval_lower_bound,
      prediction_interval_upper_bound,
      confidence_level
    FROM ML.FORECAST(
      MODEL `{model_id}`,
      STRUCT(
        {horizon} AS horizon,
        {confidence_level} AS confidence_level
      )
    )
    ORDER BY forecast_timestamp
    LIMIT {limit}
    """
    
    print(f"\n  Forecast Preview (first {limit} rows, {confidence_level*100:.0f}% intervals):")
    results = client.query(forecast_sql).result()
    
    for row in results:
        print(f"    {row.forecast_timestamp}: {row.forecast_value:.2f} mm "
              f"[{row.prediction_interval_lower_bound:.2f}, "
              f"{row.prediction_interval_upper_bound:.2f}]")


def main():
    """Main execution function."""
    client = bigquery.Client(project=PROJECT_ID)
    
    table_full_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    model_full_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_MODEL}"
    
    # Step 1: Train ARIMA_PLUS model
    create_arima_model(
        client=client,
        project_id=PROJECT_ID,
        dataset_id=BQ_DATASET,
        model_id=BQ_MODEL,
        table_id=table_full_id,
        horizon=HORIZON
    )
    
    # Step 2: Evaluate model
    evaluate_model(client, model_full_id)
    
    # Step 3: Generate forecast preview
    generate_forecast(
        client=client,
        model_id=model_full_id,
        horizon=HORIZON,
        confidence_level=CONFIDENCE_LEVEL,
        limit=10
    )
    
    print("\n✓ Step 5 Complete: BQML model trained and ready")
    print(f"  Model: {model_full_id}")
    print(f"  Forecast horizon: {HORIZON} time steps")


if __name__ == "__main__":
    main()
```

---

### 5.3 Execution

```bash
python src/pixel_planet/train_bqml_model.py
```

**Expected Duration:** 5-15 minutes (model training)

---

### 5.4 Validation

**Check model exists:**
```bash
bq ls --project_id=YOUR_PROJECT --dataset_id=weather --models
```

**Query model metadata:**
```sql
SELECT *
FROM `YOUR_PROJECT.weather.INFORMATION_SCHEMA.MODELS`
WHERE model_name = 'rain_arima'
```

**Generate full forecast:**
```sql
SELECT
  forecast_timestamp,
  forecast_value,
  prediction_interval_lower_bound,
  prediction_interval_upper_bound
FROM ML.FORECAST(
  MODEL `YOUR_PROJECT.weather.rain_arima`,
  STRUCT(168 AS horizon, 0.90 AS confidence_level)
)
ORDER BY forecast_timestamp
```

**Success Criteria:**
- ✓ Model training completes without errors
- ✓ Evaluation metrics show reasonable fit (check AIC, variance)
- ✓ Forecast generates predictions with intervals
- ✓ Prediction intervals are non-negative and reasonable

---

## Phase 6: Integration & Productionization

### 6.1 Orchestration Script

**File:** `src/pixel_planet/run_pipeline.py`

```python
"""
Full pipeline orchestration: S3 → GCS → Parquet → BigQuery → BQML
"""
import sys
from build_manifest import main as build_manifest
from run_sts_transfer import main as run_sts
from zarr_to_parquet import main as zarr_to_parquet
from load_to_bigquery import main as load_to_bq
from train_bqml_model import main as train_model

def main():
    """Run all pipeline steps sequentially."""
    steps = [
        ("Step 1: Build TSV Manifest", build_manifest),
        ("Step 2: Transfer S3 → GCS", run_sts),
        ("Step 3: Zarr → Parquet", zarr_to_parquet),
        ("Step 4: Load to BigQuery", load_to_bq),
        ("Step 5: Train BQML Model", train_model)
    ]
    
    for i, (step_name, step_func) in enumerate(steps, 1):
        print(f"\n{'='*70}")
        print(f"EXECUTING: {step_name}")
        print(f"{'='*70}\n")
        
        try:
            step_func()
        except Exception as e:
            print(f"\n✗ {step_name} FAILED: {e}")
            sys.exit(1)
    
    print(f"\n{'='*70}")
    print("✓ PIPELINE COMPLETE")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
```

**Execute full pipeline:**
```bash
python src/pixel_planet/run_pipeline.py
```

---

### 6.2 Configuration Management

**File:** `src/pixel_planet/config.py`

```python
"""
Central configuration for NASA POWER → GCP pipeline
"""
import os

# ============================================================================
# GCP Configuration
# ============================================================================
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project")
PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "YOUR_PROJECT_NUMBER")
REGION = os.getenv("GCP_REGION", "us-central1")
DEST_BUCKET = os.getenv("GCS_BUCKET", "your-gcs-bucket")

# ============================================================================
# NASA POWER S3 Configuration
# ============================================================================
S3_BUCKET = "nasa-power"
S3_REGION = "us-west-2"

# Zarr dataset selection (daily precipitation example)
# See: https://power.larc.nasa.gov/docs/services/api/
ZARR_PREFIX = os.getenv(
    "ZARR_PREFIX",
    "syn1deg/temporal/power_syn1deg_daily_temporal_precip.zarr/"
)
VAR_NAME = os.getenv("VAR_NAME", "PRECTOTCORR")

# ============================================================================
# GCS Path Structure
# ============================================================================
MANIFEST_GCS_PATH = f"gs://{DEST_BUCKET}/manifests/power_zarr.tsv"
DEST_PREFIX = "power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/"
PARQUET_OUT = f"gs://{DEST_BUCKET}/processed/davao_precip_2025.parquet"

# ============================================================================
# Spatial/Temporal Configuration
# ============================================================================
# Area of Interest (AOI) - Davao City, Philippines
LAT_MIN = float(os.getenv("LAT_MIN", "7.0"))
LAT_MAX = float(os.getenv("LAT_MAX", "7.4"))
LON_MIN = float(os.getenv("LON_MIN", "125.2"))
LON_MAX = float(os.getenv("LON_MAX", "125.7"))

# Time range
START_DATE = os.getenv("START_DATE", "2020-01-01")
END_DATE = os.getenv("END_DATE", "2025-12-31")

# ============================================================================
# BigQuery Configuration
# ============================================================================
BQ_DATASET = os.getenv("BQ_DATASET", "weather")
BQ_TABLE = os.getenv("BQ_TABLE", "davao_precip_2025")
BQ_MODEL = os.getenv("BQ_MODEL", "rain_arima")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")

# ============================================================================
# BQML Model Configuration
# ============================================================================
HORIZON = int(os.getenv("BQML_HORIZON", "168"))  # 7 days
CONFIDENCE_LEVEL = float(os.getenv("CONFIDENCE_LEVEL", "0.90"))

# ============================================================================
# Derived Paths
# ============================================================================
ZARR_GCS_URL = f"gs://{DEST_BUCKET}/{DEST_PREFIX.rstrip('/')}"
BQ_TABLE_FULL_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
BQ_MODEL_FULL_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_MODEL}"
```

**Usage:**
```python
from pixel_planet.config import PROJECT_ID, DEST_BUCKET, LAT_MIN
```

---

### 6.3 Error Handling & Logging

**Enhancement: Add structured logging to all scripts**

```python
import logging
import sys

def setup_logging(log_file: str = None) -> logging.Logger:
    """
    Configure structured logging.
    
    Args:
        log_file: Optional file path for log output
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger("nasa_power_pipeline")
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Optional file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
```

---

## Phase 7: Testing & Validation

### 7.1 End-to-End Test Checklist

```markdown
## Pipeline Validation Checklist

### Phase 1: Manifest Generation
- [ ] TSV manifest created in GCS
- [ ] First line is `TsvHttpData-1.0`
- [ ] URLs are HTTPS format and sorted
- [ ] URL count matches expected Zarr object count

### Phase 2: Storage Transfer
- [ ] STS job created successfully
- [ ] Job completes without errors
- [ ] All Zarr objects transferred to GCS
- [ ] Zarr metadata files (.zattrs, .zgroup) exist

### Phase 3: Zarr to Parquet
- [ ] Parquet file created in GCS
- [ ] Schema matches expected (ts, precip column)
- [ ] Row count matches time range
- [ ] No null values in critical columns

### Phase 4: BigQuery Load
- [ ] Table created in BigQuery
- [ ] Row count matches Parquet
- [ ] Schema correct (TIMESTAMP, FLOAT64)
- [ ] Data preview shows reasonable values

### Phase 5: BQML Training
- [ ] Model trains without errors
- [ ] Evaluation metrics are reasonable
- [ ] Forecast generates predictions
- [ ] Prediction intervals are valid

### Integration
- [ ] Full pipeline runs end-to-end
- [ ] All intermediate artifacts exist
- [ ] Final model is queryable
- [ ] Documentation is complete
```

---

### 7.2 Data Quality Tests

**File:** `tests/test_data_quality.py`

```python
"""
Data quality tests for pipeline outputs
"""
from google.cloud import bigquery
import pandas as pd

def test_bq_table_completeness(project_id: str, dataset: str, table: str):
    """Test for missing dates in time series."""
    client = bigquery.Client(project=project_id)
    
    query = f"""
    WITH date_range AS (
      SELECT MIN(ts) as start_date, MAX(ts) as end_date
      FROM `{project_id}.{dataset}.{table}`
    ),
    expected_dates AS (
      SELECT DATE(ts) as date
      FROM UNNEST(
        GENERATE_DATE_ARRAY(
          (SELECT start_date FROM date_range),
          (SELECT end_date FROM date_range)
        )
      ) as ts
    ),
    actual_dates AS (
      SELECT DISTINCT DATE(ts) as date
      FROM `{project_id}.{dataset}.{table}`
    )
    SELECT 
      COUNT(*) as missing_count
    FROM expected_dates e
    LEFT JOIN actual_dates a USING(date)
    WHERE a.date IS NULL
    """
    
    result = list(client.query(query).result())[0]
    missing_count = result.missing_count
    
    assert missing_count == 0, f"Found {missing_count} missing dates"
    print(f"✓ No missing dates in time series")


def test_bq_table_value_ranges(project_id: str, dataset: str, table: str):
    """Test for unreasonable precipitation values."""
    client = bigquery.Client(project=project_id)
    
    query = f"""
    SELECT 
      MIN(PRECTOTCORR_mm) as min_val,
      MAX(PRECTOTCORR_mm) as max_val,
      AVG(PRECTOTCORR_mm) as avg_val,
      COUNTIF(PRECTOTCORR_mm < 0) as negative_count,
      COUNTIF(PRECTOTCORR_mm > 500) as extreme_count
    FROM `{project_id}.{dataset}.{table}`
    """
    
    result = list(client.query(query).result())[0]
    
    assert result.negative_count == 0, f"Found {result.negative_count} negative values"
    assert result.extreme_count < 10, f"Found {result.extreme_count} extreme values (>500mm)"
    
    print(f"✓ Value ranges acceptable: [{result.min_val:.2f}, {result.max_val:.2f}], avg={result.avg_val:.2f}")


def test_model_forecast_validity(project_id: str, dataset: str, model: str):
    """Test that model generates valid forecasts."""
    client = bigquery.Client(project=project_id)
    
    query = f"""
    SELECT 
      COUNT(*) as forecast_count,
      COUNTIF(forecast_value IS NULL) as null_count,
      COUNTIF(prediction_interval_lower_bound > prediction_interval_upper_bound) as invalid_interval_count
    FROM ML.FORECAST(
      MODEL `{project_id}.{dataset}.{model}`,
      STRUCT(168 AS horizon, 0.90 AS confidence_level)
    )
    """
    
    result = list(client.query(query).result())[0]
    
    assert result.forecast_count == 168, f"Expected 168 forecasts, got {result.forecast_count}"
    assert result.null_count == 0, f"Found {result.null_count} null forecasts"
    assert result.invalid_interval_count == 0, f"Found {result.invalid_interval_count} invalid intervals"
    
    print(f"✓ Forecast validation passed: {result.forecast_count} valid predictions")


if __name__ == "__main__":
    PROJECT_ID = "your-gcp-project"
    DATASET = "weather"
    TABLE = "davao_precip_2025"
    MODEL = "rain_arima"
    
    print("Running data quality tests...\n")
    
    test_bq_table_completeness(PROJECT_ID, DATASET, TABLE)
    test_bq_table_value_ranges(PROJECT_ID, DATASET, TABLE)
    test_model_forecast_validity(PROJECT_ID, DATASET, MODEL)
    
    print("\n✓ All data quality tests passed")
```

---

## Phase 8: Documentation & Handoff

### 8.1 Architecture Documentation

**File:** `docs/ARCHITECTURE.md`

```markdown
# NASA POWER → GCP Pipeline Architecture

## System Overview

This pipeline ingests NASA POWER precipitation data from AWS S3, processes it through Google Cloud Platform, and trains a time-series forecasting model in BigQuery ML.

## Components

### 1. Data Source: NASA POWER on AWS S3
- **Bucket:** `s3://nasa-power` (public, no credentials needed)
- **Format:** Zarr (columnar array storage)
- **Access:** HTTP(S) via unsigned boto3 requests
- **Dataset:** Daily precipitation (syn1deg resolution)

### 2. Data Transfer: Google Cloud Storage Transfer Service
- **Method:** HTTP data source with URL list (TSV manifest)
- **Advantages:** Managed, parallel, automatic retry
- **No AWS credentials required** (uses public HTTPS URLs)

### 3. Data Processing: Zarr → Parquet
- **Tools:** xarray (Zarr reader), pandas (transformation), pyarrow (Parquet writer)
- **Transformations:**
  - Spatial subsetting (lat/lon bounds)
  - Temporal subsetting (date range)
  - Spatial aggregation (mean over grid cells)
  - Format conversion (Zarr → Parquet)

### 4. Data Warehouse: Google BigQuery
- **Table:** `{project}.weather.davao_precip_2025`
- **Schema:** `ts TIMESTAMP, PRECTOTCORR_mm FLOAT64`
- **Features:** Columnar storage, SQL interface, ML integration

### 5. ML Training: BigQuery ML (BQML)
- **Model Type:** ARIMA_PLUS
- **Capabilities:** Automatic seasonality, prediction intervals, SQL interface
- **Output:** 168-hour forecast with 90% confidence bands

## Data Flow Diagram

```
[NASA POWER S3]
      |
      | (boto3 list_objects)
      ↓
[TSV Manifest] ──→ [GCS Bucket]
      |
      | (Storage Transfer Service)
      ↓
[Zarr Store in GCS]
      |
      | (xarray + fsspec)
      ↓
[Parquet File in GCS]
      |
      | (BigQuery load_table_from_uri)
      ↓
[BigQuery Table]
      |
      | (CREATE MODEL ARIMA_PLUS)
      ↓
[BQML Model] ──→ [ML.FORECAST()] ──→ [Predictions + Intervals]
```

## Cost Considerations

### Data Transfer
- **S3 Egress:** ~$0.09/GB (first 10 TB)
- **GCS Ingress:** Free
- **Typical Zarr size:** 10-50 GB (depending on resolution/variables)

### GCS Storage
- **Standard class:** $0.020/GB/month
- **Typical usage:** 50-100 GB (Zarr + Parquet)

### BigQuery
- **Storage:** $0.020/GB/month (active), $0.010/GB/month (long-term)
- **Query:** $5/TB scanned
- **BQML Training:** $250/TB processed

### Estimated Monthly Cost
- Storage: $2-5
- Processing: $10-20 (initial run), $0-5 (subsequent queries)
- **Total:** $15-30/month for active development

## Security Considerations

- **GCS Buckets:** Private by default, IAM-controlled
- **BigQuery:** Row-level security available if needed
- **Credentials:** Application Default Credentials (ADC) or service account keys
- **STS Service Agent:** Requires explicit IAM grants

## Scaling Considerations

### Horizontal Scaling (Multiple Locations)
- Parameterize AOI coordinates
- Run pipeline in parallel for different locations
- Aggregate results in single BigQuery dataset

### Temporal Scaling (More Historical Data)
- Adjust `START_DATE` in configuration
- BigQuery handles large tables efficiently
- BQML training time increases linearly

### Variable Scaling (Multiple Weather Variables)
- Modify `VAR_NAME` configuration
- Create separate Parquet files per variable
- Train multivariate models in BQML (ARIMA_PLUS_XREG)

## Maintenance

### Routine Tasks
- **Monthly:** Update with latest NASA POWER data
- **Quarterly:** Re-train BQML model with extended history
- **Annually:** Review and optimize GCS storage classes

### Monitoring
- STS job status (Cloud Console → Storage Transfer Service)
- BigQuery table size and query costs (Cloud Console → BigQuery)
- BQML model metrics (ML.EVALUATE query)

## Troubleshooting

### Common Issues

**Issue:** STS job fails with permission denied
**Solution:** Verify STS service agent has roles/storage.objectViewer and roles/storage.objectAdmin

**Issue:** Zarr read fails with "No such file"
**Solution:** Check that STS completed successfully; verify object count in GCS

**Issue:** BQML training fails with "Insufficient data"
**Solution:** Ensure at least 2 years of historical data; check for gaps

**Issue:** Forecast values are unrealistic
**Solution:** Verify data quality (no nulls, reasonable ranges); re-train with more data

## References

- [NASA POWER Documentation](https://power.larc.nasa.gov/docs/)
- [GCS Storage Transfer Service](https://cloud.google.com/storage-transfer/docs)
- [BigQuery ML ARIMA_PLUS](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-create-time-series)
- [xarray Zarr Integration](https://docs.xarray.dev/en/stable/user-guide/io.html#zarr)
```

---

### 8.2 Operational Runbook

**File:** `docs/RUNBOOK.md`

```markdown
# NASA POWER Pipeline Operational Runbook

## Quick Start

### Prerequisites Verified?
```bash
# Check GCP authentication
gcloud auth list

# Check enabled APIs
gcloud services list --enabled | grep -E "(storagetransfer|storage|bigquery)"

# Check GCS bucket exists
gsutil ls gs://YOUR_BUCKET_NAME/
```

### Run Full Pipeline
```bash
cd /Users/kyle/Desktop/pixel-planet-101
python src/pixel_planet/run_pipeline.py
```

---

## Step-by-Step Execution

### Step 1: Generate Manifest (2-5 minutes)
```bash
python src/pixel_planet/build_manifest.py
```

**Expected output:** `Wrote manifest to gs://.../manifests/power_zarr.tsv`

**Verification:**
```bash
gsutil cat gs://YOUR_BUCKET/manifests/power_zarr.tsv | head -5
```

---

### Step 2: Transfer Data (10-30 minutes)
```bash
python src/pixel_planet/run_sts_transfer.py
```

**Expected output:** `Transfer completed successfully`

**Verification:**
```bash
gsutil ls gs://YOUR_BUCKET/power_ard_mirror/power_syn1deg_daily_temporal_precip.zarr/ | head -10
```

---

### Step 3: Convert to Parquet (2-5 minutes)
```bash
python src/pixel_planet/zarr_to_parquet.py
```

**Expected output:** `Parquet file written`

**Verification:**
```bash
gsutil ls -lh gs://YOUR_BUCKET/processed/davao_precip_2025.parquet
```

---

### Step 4: Load to BigQuery (10-30 seconds)
```bash
python src/pixel_planet/load_to_bigquery.py
```

**Expected output:** `Data loaded to BigQuery`

**Verification:**
```bash
bq query --use_legacy_sql=false \
"SELECT COUNT(*) FROM \`YOUR_PROJECT.weather.davao_precip_2025\`"
```

---

### Step 5: Train Model (5-15 minutes)
```bash
python src/pixel_planet/train_bqml_model.py
```

**Expected output:** `Model trained successfully`

**Verification:**
```bash
bq ls --project_id=YOUR_PROJECT --dataset_id=weather --models
```

---

## Configuration Updates

### Change Area of Interest (AOI)
Edit `src/pixel_planet/config.py`:
```python
LAT_MIN, LAT_MAX = 34.0, 34.2  # Example: Los Angeles
LON_MIN, LON_MAX = -118.5, -118.3
```

### Change Time Range
Edit `src/pixel_planet/config.py`:
```python
START_DATE = "2015-01-01"
END_DATE = "2024-12-31"
```

### Change Forecast Horizon
Edit `src/pixel_planet/config.py`:
```python
HORIZON = 336  # 14 days instead of 7
```

---

## Querying the Model

### Generate Forecast
```sql
SELECT
  forecast_timestamp,
  forecast_value,
  prediction_interval_lower_bound,
  prediction_interval_upper_bound
FROM ML.FORECAST(
  MODEL `YOUR_PROJECT.weather.rain_arima`,
  STRUCT(168 AS horizon, 0.90 AS confidence_level)
)
ORDER BY forecast_timestamp
```

### Export Forecast to CSV
```bash
bq query --use_legacy_sql=false --format=csv \
"SELECT * FROM ML.FORECAST(MODEL \`YOUR_PROJECT.weather.rain_arima\`, STRUCT(168 AS horizon, 0.90 AS confidence_level))" \
> forecast_output.csv
```

---

## Cleanup

### Delete Pipeline Artifacts
```bash
# Delete GCS objects
gsutil -m rm -r gs://YOUR_BUCKET/manifests/
gsutil -m rm -r gs://YOUR_BUCKET/power_ard_mirror/
gsutil -m rm -r gs://YOUR_BUCKET/processed/

# Delete BigQuery table and model
bq rm -f -t YOUR_PROJECT:weather.davao_precip_2025
bq rm -f -m YOUR_PROJECT:weather.rain_arima

# Delete dataset (if empty)
bq rm -f -d YOUR_PROJECT:weather
```

---

## Troubleshooting

### STS Job Stuck in "Queued"
**Cause:** Service agent permissions not configured
**Solution:**
```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT --format="value(projectNumber)")
gsutil iam ch serviceAccount:project-${PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://YOUR_BUCKET
```

### Zarr Read Error: "Consolidated metadata not found"
**Cause:** Incomplete transfer or corrupted Zarr store
**Solution:** Re-run STS transfer (Step 2)

### BQML Training Error: "Not enough data"
**Cause:** Time series too short
**Solution:** Extend `START_DATE` to include at least 2 years of data

### Forecast Shows Constant Value
**Cause:** Model didn't detect seasonality
**Solution:** Check data quality; ensure sufficient historical data; try manual ARIMA parameters

---

## Performance Optimization

### Faster Zarr Reads
- Use Zarr consolidated metadata (already enabled)
- Reduce AOI size
- Use temporal chunking for large date ranges

### Reduce BigQuery Costs
- Partition table by date: `PARTITION BY DATE(ts)`
- Cluster by forecast-relevant columns
- Use preview/LIMIT in development queries

### Parallel Processing Multiple Locations
```python
# Example: Process multiple cities in parallel
from multiprocessing import Pool

locations = [
    {"name": "davao", "lat_min": 7.0, "lat_max": 7.4, "lon_min": 125.2, "lon_max": 125.7},
    {"name": "manila", "lat_min": 14.5, "lat_max": 14.7, "lon_min": 120.9, "lon_max": 121.1},
    # Add more...
]

def process_location(loc):
    # Set config for this location
    # Run pipeline steps 3-5
    pass

with Pool(processes=4) as pool:
    pool.map(process_location, locations)
```

---

## Maintenance Schedule

### Weekly
- [ ] Check STS job logs for errors
- [ ] Verify BigQuery table row count growth

### Monthly
- [ ] Update pipeline with latest NASA POWER data
- [ ] Review BigQuery storage costs
- [ ] Archive old Parquet files if not needed

### Quarterly
- [ ] Re-train BQML model with extended history
- [ ] Evaluate model metrics and adjust if needed
- [ ] Review and optimize GCS bucket lifecycle policies

### Annually
- [ ] Audit IAM permissions
- [ ] Review security best practices
- [ ] Update Python dependencies

---

## Support Resources

- **NASA POWER API Docs:** https://power.larc.nasa.gov/docs/
- **GCP Storage Transfer:** https://cloud.google.com/storage-transfer/docs
- **BigQuery ML:** https://cloud.google.com/bigquery-ml/docs
- **Team Contact:** [Your contact info]
```

---

## Summary: Implementation Plan Overview

This implementation plan provides:

### ✓ **Phase 0:** Prerequisites & Environment Setup
- Configuration constants
- API enablement
- Authentication setup
- STS permissions
- Python dependencies
- GCS bucket creation

### ✓ **Phase 1:** Build TSV URL Manifest
- List S3 objects (boto3 unsigned)
- Generate HTTPS URLs
- Write TSV to GCS
- Validation steps

### ✓ **Phase 2:** Storage Transfer Service (S3 → GCS)
- Create STS job (HTTP data source)
- Trigger execution
- Monitor completion
- Validation steps

### ✓ **Phase 3:** Zarr → Parquet Conversion
- Open Zarr with xarray
- Subset by AOI and time
- Aggregate spatially
- Write Parquet to GCS
- Validation steps

### ✓ **Phase 4:** Load Parquet → BigQuery
- Create dataset
- Load Parquet (autodetect schema)
- Validate table
- Preview data

### ✓ **Phase 5:** Train BQML ARIMA_PLUS Model
- CREATE MODEL SQL
- Evaluate metrics
- Generate forecast with intervals
- Validation queries

### ✓ **Phase 6:** Integration & Productionization
- Orchestration script
- Configuration management
- Error handling & logging

### ✓ **Phase 7:** Testing & Validation
- End-to-end checklist
- Data quality tests
- Model validation tests

### ✓ **Phase 8:** Documentation & Handoff
- Architecture documentation
- Operational runbook
- Troubleshooting guide

---

## Context Engineering Best Practices Applied

1. **Explicit Prerequisites:** Every phase lists required setup and validation commands
2. **Success Criteria:** Each step includes verification commands and expected outputs
3. **Configuration Centralization:** All constants grouped in `config.py` with environment variable support
4. **Error Handling:** Structured logging and try/catch patterns throughout
5. **Dependencies Marked:** Steps clearly indicate when previous steps must complete
6. **Validation Commands:** Every phase includes CLI commands to verify success
7. **Reference Links:** External documentation linked where relevant
8. **Incremental Execution:** Each phase can be run independently after prerequisites
9. **Troubleshooting Guide:** Common issues and solutions documented
10. **Code Comments:** Inline documentation explaining why each step exists

---

## Next Steps for AI Agent Execution

1. **Review Configuration:** Update all `YOUR_PROJECT_ID`, `YOUR_BUCKET_NAME` placeholders in `config.py`
2. **Execute Phase 0:** Run all prerequisite commands to verify environment
3. **Run Pipeline:** Execute `run_pipeline.py` or individual phase scripts
4. **Monitor Progress:** Check validation commands after each phase
5. **Verify Results:** Run data quality tests from Phase 7
6. **Document Customizations:** Update this plan with any project-specific adjustments

**Estimated Total Time:** 
- First run: 45-90 minutes (including STS transfer and BQML training)
- Subsequent runs: 10-30 minutes (cached Zarr, faster processing)

---

## File Structure Summary

```
/Users/kyle/Desktop/pixel-planet-101/
├── src/pixel_planet/
│   ├── __init__.py
│   ├── config.py                    # Central configuration
│   ├── build_manifest.py            # Phase 1: TSV generation
│   ├── run_sts_transfer.py          # Phase 2: STS job
│   ├── zarr_to_parquet.py           # Phase 3: Zarr → Parquet
│   ├── load_to_bigquery.py          # Phase 4: BQ load
│   ├── train_bqml_model.py          # Phase 5: BQML training
│   └── run_pipeline.py              # Full orchestration
├── tests/
│   └── test_data_quality.py         # Data validation tests
├── docs/
│   ├── ARCHITECTURE.md              # System architecture
│   └── RUNBOOK.md                   # Operations guide
├── context_engineering/
│   └── IMPLEMENTATION_PLAN_NASA_POWER_GCP_PIPELINE.md  # This document
├── requirements.txt                 # Python dependencies
└── pyproject.toml                   # Project metadata
```

---

**Document Version:** 1.0  
**Last Updated:** 2025-10-04  
**Maintained By:** Pixel Planet 101 Team  
**For:** NASA Space Apps Challenge 2025
```

This implementation plan is now ready for an AI agent to execute. It includes:
- **Clear step-by-step instructions** with validation at each stage
- **All configuration centralized** with environment variable support
- **Complete code implementations** for all 5 pipeline phases
- **Comprehensive testing and validation** procedures
- **Operational documentation** for ongoing maintenance
- **Context engineering best practices** throughout (explicit dependencies, success criteria, error handling)

The plan can be followed sequentially by an AI agent or human developer with minimal ambiguity, and every step includes verification commands to ensure correctness before proceeding.
