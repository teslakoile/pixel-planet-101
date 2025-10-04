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

