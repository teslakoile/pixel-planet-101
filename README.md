# Pixel Planet 101: NASA POWER → BigQuery ML Pipeline

**NASA Space Apps Challenge 2025 - "Will It Rain on My Parade?"**

An end-to-end data pipeline that transfers NASA POWER precipitation data from AWS S3 to Google Cloud Platform, processes it through BigQuery, and trains a machine learning model for 7-day weather forecasting with prediction intervals.

## 🚀 Quick Start

```bash
# 1. Configure your GCP project
export GCP_PROJECT_ID="your-project-id"
export GCS_BUCKET="your-bucket-name"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline
python src/pixel_planet/run_pipeline.py
```

## 📋 Features

- ✅ **Automated S3 → GCS Transfer**: Uses Storage Transfer Service to mirror NASA POWER Zarr data
- ✅ **Zarr to Parquet Conversion**: Spatial/temporal subsetting with xarray
- ✅ **BigQuery Integration**: Automatic schema detection and loading
- ✅ **ML Time-Series Forecasting**: ARIMA_PLUS model with 90% confidence intervals
- ✅ **168-Hour Forecasts**: 7-day precipitation predictions with uncertainty bounds

## 📁 Project Structure

```
pixel-planet-101/
├── src/pixel_planet/
│   ├── config.py                    # Central configuration
│   ├── build_manifest.py            # Phase 1: TSV manifest generation
│   ├── run_sts_transfer.py          # Phase 2: Storage Transfer Service
│   ├── zarr_to_parquet.py           # Phase 3: Zarr → Parquet conversion
│   ├── load_to_bigquery.py          # Phase 4: BigQuery load
│   ├── train_bqml_model.py          # Phase 5: BQML model training
│   └── run_pipeline.py              # Full orchestration
├── tests/
│   └── test_data_quality.py         # Data validation tests
├── docs/
│   ├── ARCHITECTURE.md              # System architecture
│   ├── RUNBOOK.md                   # Operations guide
│   └── SETUP_GUIDE.md               # Detailed setup instructions
├── context_engineering/
│   └── IMPLEMENTATION_PLAN_NASA_POWER_GCP_PIPELINE.md
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

## 🛠️ Setup

### Prerequisites

- Google Cloud Platform account
- Python 3.8+
- `gcloud` CLI installed and configured

### Detailed Setup Instructions

See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) for complete setup instructions.

**Quick Setup:**

1. **Enable GCP APIs:**
   ```bash
   gcloud services enable storagetransfer.googleapis.com storage.googleapis.com bigquery.googleapis.com
   ```

2. **Create GCS Bucket:**
   ```bash
   gsutil mb -p YOUR_PROJECT gs://YOUR_BUCKET/
   ```

3. **Configure Credentials:**
   ```bash
   gcloud auth application-default login
   ```

4. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 🎯 Usage

### Run Individual Phases

```bash
# Phase 1: Build manifest
python src/pixel_planet/build_manifest.py

# Phase 2: Transfer S3 → GCS (10-30 min)
python src/pixel_planet/run_sts_transfer.py

# Phase 3: Zarr → Parquet (2-5 min)
python src/pixel_planet/zarr_to_parquet.py

# Phase 4: Load to BigQuery
python src/pixel_planet/load_to_bigquery.py

# Phase 5: Train ML model (5-15 min)
python src/pixel_planet/train_bqml_model.py
```

### Run Full Pipeline

```bash
python src/pixel_planet/run_pipeline.py
```

### Query Forecasts

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

## ⚙️ Configuration

Edit `src/pixel_planet/config.py` or set environment variables:

```python
# GCP Settings
GCP_PROJECT_ID = "your-project-id"
GCS_BUCKET = "your-bucket-name"

# Area of Interest (Davao City, Philippines by default)
LAT_MIN, LAT_MAX = 7.0, 7.4
LON_MIN, LON_MAX = 125.2, 125.7

# Time Range
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"

# Forecast Settings
HORIZON = 168  # 7 days
CONFIDENCE_LEVEL = 0.90  # 90% prediction intervals
```

## 📊 Architecture

The pipeline consists of 5 main phases:

1. **Manifest Generation**: List NASA POWER S3 objects and create TSV URL list
2. **Data Transfer**: Use GCP Storage Transfer Service to copy Zarr data
3. **Data Processing**: Subset and convert Zarr to Parquet format
4. **BigQuery Load**: Import Parquet data into BigQuery table
5. **ML Training**: Train ARIMA_PLUS model with prediction intervals

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## 🧪 Testing

Run data quality tests:

```bash
python tests/test_data_quality.py
```

Tests include:
- Time series completeness (no missing dates)
- Value range validation (reasonable precipitation values)
- Model forecast validity (valid prediction intervals)

## 📚 Documentation

- **[SETUP_GUIDE.md](docs/SETUP_GUIDE.md)**: Detailed setup instructions
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)**: System architecture and design
- **[RUNBOOK.md](docs/RUNBOOK.md)**: Operational procedures and troubleshooting
- **[IMPLEMENTATION_PLAN](context_engineering/IMPLEMENTATION_PLAN_NASA_POWER_GCP_PIPELINE.md)**: Comprehensive implementation plan

## 💰 Cost Estimation

- **First run:** $10-20 (includes data transfer and ML training)
- **Monthly updates:** $15-30
- **Storage only:** $2-5/month

Set up [GCP billing alerts](https://cloud.google.com/billing/docs/how-to/budgets) to monitor costs.

## 🔧 Troubleshooting

### Common Issues

**STS Job Stuck:**
```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT --format="value(projectNumber)")
gsutil iam ch serviceAccount:project-${PROJECT_NUMBER}@storage-transfer-service.iam.gserviceaccount.com:roles/storage.objectAdmin gs://YOUR_BUCKET
```

**Import Errors:**
```bash
pip install --upgrade -r requirements.txt
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for more troubleshooting tips.

## 🌍 NASA Space Apps Challenge

**Challenge:** "Will It Rain on My Parade?"

**Solution:** This pipeline provides:
- Access to 40+ years of NASA POWER precipitation data
- Machine learning forecasts with uncertainty quantification
- 7-day ahead predictions for event planning
- Scalable architecture for global deployment

## 📝 License

This project is developed for NASA Space Apps Challenge 2025.

## 🤝 Contributing

This project was built following the implementation plan in `context_engineering/IMPLEMENTATION_PLAN_NASA_POWER_GCP_PIPELINE.md`.

## 🔗 References

- [NASA POWER API](https://power.larc.nasa.gov/docs/)
- [Google Cloud Storage Transfer Service](https://cloud.google.com/storage-transfer/docs)
- [BigQuery ML ARIMA_PLUS](https://cloud.google.com/bigquery-ml/docs/reference/standard-sql/bigqueryml-syntax-create-time-series)
- [xarray Zarr Documentation](https://docs.xarray.dev/en/stable/user-guide/io.html#zarr)
