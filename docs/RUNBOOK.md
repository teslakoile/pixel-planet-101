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
- **Project Repository:** /Users/kyle/Desktop/pixel-planet-101

