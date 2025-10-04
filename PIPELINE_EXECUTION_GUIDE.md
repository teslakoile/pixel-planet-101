# Weather Forecasting Pipeline - Step-by-Step Execution Guide

## 📋 Overview

This pipeline fetches historical weather data from NASA POWER API, trains BigQuery ML ARIMA models, and generates 2-week forecasts for multiple locations and weather parameters.

### Architecture Summary
- **Data:** 1 unified table with all locations and weather attributes
- **Models:** 6 ARIMA models (1 per weather attribute, each handling all locations)
- **Forecasts:** 1 unified table with all forecast results
- **Locations:** 5 global cities (Davao, Cebu, Manila, New York, Beijing)
- **Attributes:** 6 weather parameters (precipitation, temperature, wind, humidity, solar radiation, cloud cover)

---

## 🎯 Final BigQuery Structure

```
Dataset: weather
│
├── 📊 weather_data (raw historical data)
│   └── Columns: ts, lat, lon, location_name, precipitation_mm, temperature_2m_c,
│                 windspeed_10m_ms, humidity_2m_pct, solar_radiation_wm2, cloud_cover_pct
│
├── 🤖 Models (6 ARIMA models)
│   ├── precipitation_arima (predicts for all 5 locations)
│   ├── temperature_arima (predicts for all 5 locations)
│   ├── wind_arima (predicts for all 5 locations)
│   ├── humidity_arima (predicts for all 5 locations)
│   ├── solar_arima (predicts for all 5 locations)
│   └── cloud_arima (predicts for all 5 locations)
│
└── 📈 forecast_results (unified forecast table)
    └── Columns: forecast_timestamp, lat, lon, parameter, forecast_value,
                 prediction_interval_lower, prediction_interval_upper, confidence_level,
                 forecast_date, forecast_hour, day_name
```

---

## 🔧 Prerequisites

### 1. Environment Setup
```bash
# Ensure you're in the project directory
cd /Users/kyle/Desktop/pixel-planet-101

# Activate virtual environment
source .venv/bin/activate

# Verify Python packages are installed
pip list | grep -E "google-cloud-bigquery|google-cloud-storage|pandas|pyarrow|gcsfs|requests"
```

### 2. GCP Authentication
```bash
# Check current authentication
gcloud auth list

# If not authenticated, login
gcloud auth login

# Set active project
gcloud config set project YOUR_PROJECT_ID

# Verify project is set
gcloud config get-value project
```

### 3. Environment Variables
Ensure `.env` file exists with:
```bash
GCP_PROJECT_ID=your-project-id
GCP_PROJECT_NUMBER=your-project-number
GCS_BUCKET=your-bucket-name
```

Load environment variables:
```bash
# Check if .env exists
ls -la .env

# Source it (if needed)
export $(cat .env | xargs)
```

### 4. Verify GCP Resources
```bash
# Check if BigQuery dataset exists
bq ls --project_id=$(gcloud config get-value project) weather

# If not, create it
bq mk --dataset --location=US $(gcloud config get-value project):weather

# Check if GCS bucket exists
gsutil ls gs://YOUR_BUCKET_NAME

# If not, create it
gsutil mb -l US gs://YOUR_BUCKET_NAME
```

---

## 📍 Step 0: Update Configuration

### Task: Configure 5 specific locations

**File to modify:** `src/pixel_planet/config.py`

**Changes needed:**

1. **Replace grid-based spatial config with specific locations** (around line 106-114):

```python
# ============================================================================
# Spatial/Temporal Configuration
# ============================================================================
# Specific Points of Interest (5 global cities)
LOCATIONS = {
    'davao_city': {
        'name': 'Davao City, Philippines',
        'lat': 7.07,
        'lon': 125.61
    },
    'cebu_city': {
        'name': 'Cebu City, Philippines', 
        'lat': 10.32,
        'lon': 123.90
    },
    'manila': {
        'name': 'Manila, Philippines',
        'lat': 14.60,
        'lon': 120.98
    },
    'new_york': {
        'name': 'New York City, USA',
        'lat': 40.71,
        'lon': -74.01
    },
    'beijing': {
        'name': 'Beijing, China',
        'lat': 39.90,
        'lon': 116.40
    }
}
```

2. **Update model names to use ARIMA** (around line 55-85):

```python
ML_MODELS = {
    'precipitation': {
        'target': 'PRECTOTCORR',
        'model_name': 'precipitation_arima',
        'column': 'precipitation_mm',
    },
    'temperature': {
        'target': 'T2M',
        'model_name': 'temperature_arima',
        'column': 'temperature_2m_c',
    },
    'wind': {
        'target': 'WS10M',
        'model_name': 'wind_arima',
        'column': 'windspeed_10m_ms',
    },
    'humidity': {
        'target': 'RH2M',
        'model_name': 'humidity_arima',
        'column': 'humidity_2m_pct',
    },
    'solar_radiation': {
        'target': 'ALLSKY_SFC_SW_DWN',
        'model_name': 'solar_arima',
        'column': 'solar_radiation_wm2',
    },
    'cloud_cover': {
        'target': 'CLOUD_AMT',
        'model_name': 'cloud_arima',
        'column': 'cloud_cover_pct',
    },
}
```

3. **Update BQ_MODELS** (around line 146-153):

```python
BQ_MODELS = {
    'precipitation': os.getenv("BQ_MODEL_PRECIP", "precipitation_arima"),
    'temperature': os.getenv("BQ_MODEL_TEMP", "temperature_arima"),
    'wind': os.getenv("BQ_MODEL_WIND", "wind_arima"),
    'humidity': os.getenv("BQ_MODEL_HUMIDITY", "humidity_arima"),
    'solar_radiation': os.getenv("BQ_MODEL_UV", "solar_arima"),
    'cloud_cover': os.getenv("BQ_MODEL_CLOUD", "cloud_arima"),
}
```

**File to modify:** `src/pixel_planet/fetch_power_api.py`

**Changes needed:**

1. **Replace `fetch_aoi_data()` with `fetch_specific_locations()`**:

```python
def fetch_specific_locations(
    locations: dict,
    start_date: str,
    end_date: str,
    parameters: List[str]
) -> pd.DataFrame:
    """
    Fetch data for specific locations (not a grid).
    
    Args:
        locations: Dict of location configs with lat/lon
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        parameters: List of NASA POWER parameters
        
    Returns:
        DataFrame with columns: ts, lat, lon, location_name, [parameter columns]
    """
    all_data = []
    
    for location_id, location_info in locations.items():
        lat = location_info['lat']
        lon = location_info['lon']
        name = location_info['name']
        
        print(f"\n📍 Fetching: {name}")
        print(f"   Coordinates: ({lat:.2f}, {lon:.2f})")
        
        try:
            data = fetch_power_data(lat, lon, start_date, end_date, parameters)
            
            if 'properties' in data and 'parameter' in data['properties']:
                param_dict = data['properties']['parameter']
                
                # Build dataframe from first parameter
                first_param = parameters[0]
                df_point = pd.DataFrame(
                    list(param_dict[first_param].items()), 
                    columns=['timestamp', first_param]
                )
                
                # Merge other parameters
                for param in parameters[1:]:
                    if param in param_dict:
                        df_param = pd.DataFrame(
                            list(param_dict[param].items()), 
                            columns=['timestamp', param]
                        )
                        df_point = df_point.merge(df_param, on='timestamp', how='left')
                
                df_point['lat'] = lat
                df_point['lon'] = lon
                df_point['location_name'] = name
                all_data.append(df_point)
                
                print(f"   ✓ Retrieved {len(df_point):,} hourly records")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data fetched from API")
    
    # Combine all locations
    df_all = pd.concat(all_data, ignore_index=True)
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'], format='%Y%m%d%H')
    
    # Rename columns
    from pixel_planet.config import PARAMETERS
    rename_map = {'timestamp': 'ts'}
    for param in parameters:
        column_name = PARAMETERS.get(param, f'{param}_value')
        rename_map[param] = column_name
    
    df_all = df_all.rename(columns=rename_map)
    df_all = df_all.sort_values(['location_name', 'ts']).reset_index(drop=True)
    df_all['ts'] = pd.to_datetime(df_all['ts']).dt.tz_localize('UTC')
    
    return df_all
```

2. **Update `main()` function**:

```python
def main():
    """Main execution function."""
    from pixel_planet.config import LOCATIONS
    
    print("="*70)
    print("NASA POWER API - Multi-Location Data Fetch")
    print("="*70)
    print(f"Start date: {START_DATE}")
    print(f"End date: {END_DATE}")
    print(f"Locations: {len(LOCATIONS)}")
    print(f"Parameters: {len(FETCH_PARAMETERS)}")
    print()
    
    df = fetch_specific_locations(
        locations=LOCATIONS,
        start_date=START_DATE,
        end_date=END_DATE,
        parameters=FETCH_PARAMETERS
    )
    
    print(f"\n{'='*70}")
    print(f"📊 Data Summary:")
    print(f"   Total records: {len(df):,}")
    print(f"   Locations: {df['location_name'].nunique()}")
    print(f"   Date range: {df['ts'].min()} to {df['ts'].max()}")
    print(f"   Parameters: {len(FETCH_PARAMETERS)}")
    print(f"{'='*70}\n")
    
    print(f"💾 Writing to GCS: {PARQUET_OUT}")
    write_parquet_to_gcs(df, PARQUET_OUT)
    print(f"✅ Upload complete!\n")
```

3. **Update `write_parquet_to_gcs()` to include `location_name`**:

```python
def write_parquet_to_gcs(df: pd.DataFrame, gcs_path: str) -> None:
    """
    Write pandas DataFrame to Parquet file in GCS.
    """
    data_columns = [col for col in df.columns if col not in ['ts', 'lat', 'lon', 'location_name']]
    
    schema_fields = [
        pa.field('ts', pa.timestamp('us', tz='UTC')),
        pa.field('lat', pa.float64()),
        pa.field('lon', pa.float64()),
        pa.field('location_name', pa.string()),
    ]
    for col in data_columns:
        schema_fields.append(pa.field(col, pa.float64()))
    
    schema = pa.schema(schema_fields)
    df = df[['ts', 'lat', 'lon', 'location_name'] + data_columns]
    table = pa.Table.from_pandas(df, schema=schema)
    
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")
```

**File to modify:** `src/pixel_planet/load_to_bigquery.py`

**Update schema to include `location_name`** (around line 55-65):

```python
schema = [
    bigquery.SchemaField("ts", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("lat", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("lon", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("location_name", "STRING", mode="NULLABLE"),
]

# Add parameter columns dynamically
for param_name, column_name in PARAMETERS.items():
    schema.append(bigquery.SchemaField(column_name, "FLOAT64", mode="NULLABLE"))
```

**File to modify:** `src/pixel_planet/train_bqml_model.py`

**Ensure it uses `create_arima_model()` not `create_dnn_model()`**. The function should look like:

```python
def create_arima_model(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    model_id: str,
    table_id: str,
    horizon: int,
    target_column: str = None
) -> bigquery.QueryJob:
    """
    Create ARIMA_PLUS model for multi-location time-series forecasting.
    """
    model_full_id = f"{project_id}.{dataset_id}.{model_id}"
    
    if target_column is None:
        from pixel_planet.config import PARAMETERS, PRIMARY_PARAMETER
        target_column = PARAMETERS[PRIMARY_PARAMETER]
    
    print(f"Creating model: {model_full_id}")
    print(f"  Model type: ARIMA_PLUS")
    print(f"  Target column: {target_column}")
    print(f"  Horizon: {horizon} hours ({horizon/24:.1f} days)")
    print(f"  Spatial features: lat, lon (TIME_SERIES_ID_COL)")
    
    create_model_sql = f"""
    CREATE OR REPLACE MODEL `{model_full_id}`
    OPTIONS(
      MODEL_TYPE = 'ARIMA_PLUS',
      TIME_SERIES_TIMESTAMP_COL = 'ts',
      TIME_SERIES_DATA_COL = '{target_column}',
      TIME_SERIES_ID_COL = ['lat', 'lon'],
      HORIZON = {horizon},
      AUTO_ARIMA = TRUE,
      DATA_FREQUENCY = 'HOURLY'
    ) AS
    SELECT 
      ts,
      lat,
      lon,
      {target_column}
    FROM `{table_id}`
    WHERE ts >= TIMESTAMP('2022-01-01')
    ORDER BY lat, lon, ts
    """
    
    print("\n🚀 Starting ARIMA_PLUS training...")
    query_job = client.query(create_model_sql)
    query_job.result()
    
    print(f"\n✓ Model trained successfully!")
    return query_job
```

**Verification:**
```bash
# After making all changes, verify syntax
python -c "from pixel_planet import config; print('✓ Config loaded')"
python -c "from pixel_planet import fetch_power_api; print('✓ Fetch script loaded')"
python -c "from pixel_planet import train_bqml_model; print('✓ Train script loaded')"
```

---

## 📥 Step 1: Fetch Historical Weather Data

### Task: Download 3 years of hourly weather data from NASA POWER API

**Command:**
```bash
cd /Users/kyle/Desktop/pixel-planet-101
source .venv/bin/activate
python -m pixel_planet.fetch_power_api
```

**What it does:**
- Fetches hourly data for 5 locations (Davao, Cebu, Manila, NYC, Beijing)
- Retrieves 6 weather parameters per location
- Time range: Rolling 3-year window (e.g., 2021-10-01 to 2024-09-30)
- Saves to GCS: `gs://YOUR_BUCKET/processed/weather_data_hourly.parquet`

**Expected output:**
```
======================================================================
NASA POWER API - Multi-Location Data Fetch
======================================================================
Start date: 2021-10-01
End date: 2024-09-30
Locations: 5
Parameters: 6

📍 Fetching: Davao City, Philippines
   Coordinates: (7.07, 125.61)
   ✓ Retrieved 26,280 hourly records

📍 Fetching: Cebu City, Philippines
   Coordinates: (10.32, 123.90)
   ✓ Retrieved 26,280 hourly records

📍 Fetching: Manila, Philippines
   Coordinates: (14.60, 120.98)
   ✓ Retrieved 26,280 hourly records

📍 Fetching: New York City, USA
   Coordinates: (40.71, -74.01)
   ✓ Retrieved 26,280 hourly records

📍 Fetching: Beijing, China
   Coordinates: (39.90, 116.40)
   ✓ Retrieved 26,280 hourly records

======================================================================
📊 Data Summary:
   Total records: 131,400
   Locations: 5
   Date range: 2021-10-01 00:00:00+00:00 to 2024-09-30 23:00:00+00:00
   Parameters: 6
======================================================================

💾 Writing to GCS: gs://YOUR_BUCKET/processed/weather_data_hourly.parquet
✅ Upload complete!
```

**Time estimate:** 5-10 minutes (depends on NASA API response time)

**Verification:**
```bash
# Check if file exists in GCS
gsutil ls -lh gs://YOUR_BUCKET/processed/weather_data_hourly.parquet

# Should see a file ~50-100 MB in size
```

**Expected data structure:**
- Columns: `ts`, `lat`, `lon`, `location_name`, `precipitation_mm`, `temperature_2m_c`, `windspeed_10m_ms`, `humidity_2m_pct`, `solar_radiation_wm2`, `cloud_cover_pct`
- Rows: ~131,400 (5 locations × 26,280 hours)

**Troubleshooting:**
- If API rate limited: Wait 5 minutes and retry
- If timeout: Check internet connection
- If authentication error: Re-run `gcloud auth application-default login`

---

## 📊 Step 2: Load Data to BigQuery

### Task: Import Parquet file from GCS into BigQuery table

**Command:**
```bash
python -m pixel_planet.load_to_bigquery
```

**What it does:**
- Reads Parquet file from GCS
- Creates/replaces `weather.weather_data` table
- Validates schema and data types

**Expected output:**
```
======================================================================
Loading Parquet to BigQuery
======================================================================
Source: gs://YOUR_BUCKET/processed/weather_data_hourly.parquet
Destination: your-project.weather.weather_data

Starting load job...
✓ Load job complete!

Table Details:
  Rows: 131,400
  Size: 15.2 MB
  Schema:
    - ts: TIMESTAMP
    - lat: FLOAT64
    - lon: FLOAT64
    - location_name: STRING
    - precipitation_mm: FLOAT64
    - temperature_2m_c: FLOAT64
    - windspeed_10m_ms: FLOAT64
    - humidity_2m_pct: FLOAT64
    - solar_radiation_wm2: FLOAT64
    - cloud_cover_pct: FLOAT64
```

**Time estimate:** 1-2 minutes

**Verification:**
```bash
# Check table exists and has data
bq query --use_legacy_sql=false "
SELECT 
  COUNT(*) as total_rows,
  COUNT(DISTINCT location_name) as num_locations,
  MIN(ts) as min_date,
  MAX(ts) as max_date
FROM \`$(gcloud config get-value project).weather.weather_data\`
"

# Expected result:
# +------------+---------------+---------------------+---------------------+
# | total_rows | num_locations | min_date            | max_date            |
# +------------+---------------+---------------------+---------------------+
# | 131400     | 5             | 2021-10-01 00:00:00 | 2024-09-30 23:00:00 |
# +------------+---------------+---------------------+---------------------+
```

**Troubleshooting:**
- If schema mismatch: Re-run Step 1 (fetch data)
- If table not found: Check BigQuery dataset exists (`bq ls`)
- If permission denied: Check IAM roles for BigQuery

---

## 🤖 Step 3: Train ARIMA Models (6 models)

### Task: Train one ARIMA model per weather parameter

**Important:** Each model takes 10-20 minutes. Total time: 60-120 minutes.

### Option A: Train Sequentially (Safer)

**Command:**
```bash
# Train all 6 models one by one
python -m pixel_planet.train_bqml_model --target precipitation
python -m pixel_planet.train_bqml_model --target temperature
python -m pixel_planet.train_bqml_model --target wind
python -m pixel_planet.train_bqml_model --target humidity
python -m pixel_planet.train_bqml_model --target solar_radiation
python -m pixel_planet.train_bqml_model --target cloud_cover
```

**Or use the automation script:**
```bash
chmod +x train_all_models.sh
./train_all_models.sh
```

### Option B: Train in Parallel (Faster, requires quota)

**Command:**
```bash
# Run all 6 training jobs simultaneously
python -m pixel_planet.train_bqml_model --target precipitation &
python -m pixel_planet.train_bqml_model --target temperature &
python -m pixel_planet.train_bqml_model --target wind &
python -m pixel_planet.train_bqml_model --target humidity &
python -m pixel_planet.train_bqml_model --target solar_radiation &
python -m pixel_planet.train_bqml_model --target cloud_cover &

# Wait for all to complete
wait

echo "✅ All models trained!"
```

**Expected output (per model):**
```
======================================================================
TRAINING MODEL: PRECIPITATION
======================================================================
Target: precipitation
Model name: precipitation_arima
Target column: precipitation_mm
Model ID: your-project.weather.precipitation_arima

Creating model: your-project.weather.precipitation_arima
  Model type: ARIMA_PLUS
  Target column: precipitation_mm
  Horizon: 336 hours (14.0 days)
  Spatial features: lat, lon (TIME_SERIES_ID_COL)

🚀 Starting ARIMA_PLUS training...
   This will take 10-20 minutes.
   You can monitor progress in the BigQuery console:
   https://console.cloud.google.com/bigquery?project=...

   Job submitted. Waiting for completion...

✓ Model trained successfully!

======================================================================
Model Evaluation Metrics
======================================================================
... (evaluation output)
```

**Time estimate:** 
- Sequential: 60-120 minutes (10-20 min per model)
- Parallel: 10-20 minutes (if you have quota)

**Verification:**
```bash
# Check all 6 models exist
bq ls --project_id=$(gcloud config get-value project) --max_results=10 weather

# Should see:
# precipitation_arima
# temperature_arima
# wind_arima
# humidity_arima
# solar_arima
# cloud_arima
```

**Troubleshooting:**
- If "quota exceeded": Use sequential approach (Option A)
- If "not enough data" error: Check Step 2 data loaded correctly
- If training fails: Check BigQuery logs in console

---

## 📈 Step 4: Generate Unified Forecast

### Task: Create single forecast table with all parameters and locations

**Create new file:** `src/pixel_planet/batch_forecast_unified.py`

```python
"""
Generate unified forecast table for all 6 weather parameters
"""
from google.cloud import bigquery
from pixel_planet.config import (
    PROJECT_ID, BQ_DATASET, ML_MODELS, BQ_MODELS, HORIZON, CONFIDENCE_LEVEL
)

def generate_unified_forecast(
    client: bigquery.Client,
    horizon: int = 336,
    confidence_level: float = 0.9
) -> bigquery.Table:
    """
    Generate unified forecast table with all parameters.
    
    Creates weather.forecast_results with UNION ALL of 6 model forecasts.
    """
    print("="*70)
    print("GENERATING UNIFIED FORECAST")
    print("="*70)
    print(f"Models: {len(ML_MODELS)}")
    print(f"Horizon: {horizon} hours ({horizon/24:.1f} days)")
    print(f"Confidence: {confidence_level*100:.0f}%")
    print()
    
    # Build UNION ALL query dynamically
    union_parts = []
    
    for param_key, model_config in ML_MODELS.items():
        model_name = BQ_MODELS[param_key]
        model_full_id = f"{PROJECT_ID}.{BQ_DATASET}.{model_name}"
        
        print(f"  Including: {param_key} ({model_name})")
        
        union_parts.append(f"""
        SELECT
          forecast_timestamp,
          lat,
          lon,
          '{param_key}' AS parameter,
          forecast_value,
          prediction_interval_lower_bound AS prediction_interval_lower,
          prediction_interval_upper_bound AS prediction_interval_upper,
          confidence_level,
          standard_error,
          EXTRACT(DATE FROM forecast_timestamp) AS forecast_date,
          EXTRACT(HOUR FROM forecast_timestamp) AS forecast_hour,
          EXTRACT(DAYOFWEEK FROM forecast_timestamp) AS day_of_week,
          FORMAT_TIMESTAMP('%A', forecast_timestamp) AS day_name
        FROM ML.FORECAST(
          MODEL `{model_full_id}`,
          STRUCT({horizon} AS horizon, {confidence_level} AS confidence_level)
        )
        """)
    
    unified_query = f"""
    CREATE OR REPLACE TABLE `{PROJECT_ID}.{BQ_DATASET}.forecast_results` AS
    {' UNION ALL '.join(union_parts)}
    ORDER BY lat, lon, parameter, forecast_timestamp
    """
    
    print(f"\n🚀 Executing unified forecast query...")
    print("   This may take 5-10 minutes...")
    
    query_job = client.query(unified_query)
    query_job.result()
    
    table = client.get_table(f"{PROJECT_ID}.{BQ_DATASET}.forecast_results")
    
    print(f"\n✅ Unified forecast complete!")
    print(f"   Table: {PROJECT_ID}.{BQ_DATASET}.forecast_results")
    print(f"   Total rows: {table.num_rows:,}")
    print(f"   Expected: {5} locations × {6} params × {horizon} hours = {5 * 6 * horizon:,}")
    print(f"   Size: {table.num_bytes / 1024 / 1024:.2f} MB")
    print("="*70)
    
    return table

def analyze_forecast(client: bigquery.Client) -> None:
    """Quick analysis of unified forecast table."""
    
    print("\n📊 FORECAST ANALYSIS")
    print("="*70)
    
    # Summary query
    summary_query = f"""
    SELECT
      parameter,
      COUNT(*) as num_forecasts,
      COUNT(DISTINCT lat) as num_locations,
      AVG(forecast_value) as avg_value,
      MIN(forecast_value) as min_value,
      MAX(forecast_value) as max_value
    FROM `{PROJECT_ID}.{BQ_DATASET}.forecast_results`
    GROUP BY parameter
    ORDER BY parameter
    """
    
    results = client.query(summary_query).result()
    
    print(f"\n{'Parameter':<20} {'Forecasts':<12} {'Locations':<12} {'Avg':<10} {'Min':<10} {'Max':<10}")
    print("-" * 70)
    
    for row in results:
        print(f"{row.parameter:<20} {row.num_forecasts:<12} {row.num_locations:<12} {row.avg_value:<10.2f} {row.min_value:<10.2f} {row.max_value:<10.2f}")
    
    print("="*70)

def main():
    """Main execution."""
    client = bigquery.Client(project=PROJECT_ID)
    
    # Generate unified forecast
    table = generate_unified_forecast(
        client=client,
        horizon=HORIZON,
        confidence_level=CONFIDENCE_LEVEL
    )
    
    # Analyze results
    analyze_forecast(client)
    
    print(f"\n🎉 Pipeline complete!")
    print(f"\nQuery your forecasts:")
    print(f"  SELECT * FROM `{PROJECT_ID}.{BQ_DATASET}.forecast_results`")
    print(f"  WHERE lat = 7.07 AND parameter = 'precipitation'")
    print(f"  ORDER BY forecast_timestamp")

if __name__ == "__main__":
    main()
```

**Command:**
```bash
python -m pixel_planet.batch_forecast_unified
```

**Expected output:**
```
======================================================================
GENERATING UNIFIED FORECAST
======================================================================
Models: 6
Horizon: 336 hours (14.0 days)
Confidence: 90%

  Including: precipitation (precipitation_arima)
  Including: temperature (temperature_arima)
  Including: wind (wind_arima)
  Including: humidity (humidity_arima)
  Including: solar_radiation (solar_arima)
  Including: cloud_cover (cloud_arima)

🚀 Executing unified forecast query...
   This may take 5-10 minutes...

✅ Unified forecast complete!
   Table: your-project.weather.forecast_results
   Total rows: 10,080
   Expected: 5 locations × 6 params × 336 hours = 10,080
   Size: 1.25 MB
======================================================================

📊 FORECAST ANALYSIS
======================================================================

Parameter            Forecasts    Locations    Avg        Min        Max       
----------------------------------------------------------------------
cloud_cover          1680         5            65.23      20.15      95.80     
humidity             1680         5            72.45      45.20      98.50     
precipitation        1680         5            2.15       0.00       15.30     
solar_radiation      1680         5            425.67     0.00       850.25    
temperature          1680         5            26.35      -5.20      38.40     
wind                 1680         5            3.85       0.50       12.30     
======================================================================

🎉 Pipeline complete!

Query your forecasts:
  SELECT * FROM `your-project.weather.forecast_results`
  WHERE lat = 7.07 AND parameter = 'precipitation'
  ORDER BY forecast_timestamp
```

**Time estimate:** 5-10 minutes

**Verification:**
```bash
# Check forecast table exists
bq show $(gcloud config get-value project):weather.forecast_results

# Sample query
bq query --use_legacy_sql=false "
SELECT 
  parameter,
  COUNT(*) as forecast_count,
  COUNT(DISTINCT lat) as num_locations
FROM \`$(gcloud config get-value project).weather.forecast_results\`
GROUP BY parameter
ORDER BY parameter
"

# Expected: 6 rows, each with 1680 forecasts and 5 locations
```

---

## ✅ Step 5: Validate Results

### Task: Verify pipeline completed successfully

**Validation queries:**

```bash
# 1. Check raw data table
bq query --use_legacy_sql=false "
SELECT 
  'Raw Data' as stage,
  COUNT(*) as rows,
  COUNT(DISTINCT location_name) as locations,
  MIN(ts) as start_date,
  MAX(ts) as end_date
FROM \`$(gcloud config get-value project).weather.weather_data\`
"

# 2. Check models exist
bq ls $(gcloud config get-value project):weather | grep arima | wc -l
# Should output: 6

# 3. Check forecast table
bq query --use_legacy_sql=false "
SELECT 
  'Forecast' as stage,
  COUNT(*) as rows,
  COUNT(DISTINCT parameter) as parameters,
  COUNT(DISTINCT lat) as locations,
  MIN(forecast_timestamp) as start_forecast,
  MAX(forecast_timestamp) as end_forecast
FROM \`$(gcloud config get-value project).weather.forecast_results\`
"

# 4. Sample forecast for Davao City
bq query --use_legacy_sql=false "
SELECT 
  forecast_timestamp,
  parameter,
  ROUND(forecast_value, 2) as value,
  ROUND(prediction_interval_lower, 2) as lower,
  ROUND(prediction_interval_upper, 2) as upper
FROM \`$(gcloud config get-value project).weather.forecast_results\`
WHERE lat = 7.07 
  AND forecast_timestamp >= TIMESTAMP(CURRENT_DATE())
ORDER BY parameter, forecast_timestamp
LIMIT 30
"
```

**Expected validation results:**

| Check | Expected | Status |
|-------|----------|--------|
| Raw data rows | ~131,400 | ✅ |
| Locations | 5 | ✅ |
| Date range | 3 years | ✅ |
| ARIMA models | 6 | ✅ |
| Forecast rows | 10,080 | ✅ |
| Parameters | 6 | ✅ |
| Forecast horizon | 14 days | ✅ |

---

## 📊 Example Queries

### Query 1: Get all forecasts for specific location and time
```sql
SELECT 
  forecast_timestamp,
  parameter,
  ROUND(forecast_value, 2) as forecast,
  ROUND(prediction_interval_lower, 2) as lower_bound,
  ROUND(prediction_interval_upper, 2) as upper_bound
FROM `your-project.weather.forecast_results`
WHERE lat = 7.07  -- Davao City
  AND forecast_timestamp BETWEEN '2024-10-05 08:00:00' AND '2024-10-05 09:00:00'
ORDER BY parameter;
```

### Query 2: Get precipitation forecast for next 7 days (all locations)
```sql
SELECT 
  forecast_date,
  lat,
  lon,
  AVG(forecast_value) as avg_daily_precip_mm,
  MAX(forecast_value) as max_hourly_precip_mm
FROM `your-project.weather.forecast_results`
WHERE parameter = 'precipitation'
  AND forecast_timestamp >= CURRENT_TIMESTAMP()
  AND forecast_timestamp < TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY forecast_date, lat, lon
ORDER BY lat, forecast_date;
```

### Query 3: Find high-risk rain days (>5mm/hour)
```sql
SELECT 
  forecast_timestamp,
  lat,
  lon,
  ROUND(forecast_value, 2) as precip_mm_per_hour,
  day_name
FROM `your-project.weather.forecast_results`
WHERE parameter = 'precipitation'
  AND forecast_value > 5.0
ORDER BY forecast_value DESC
LIMIT 20;
```

### Query 4: Multi-parameter forecast for specific event planning
```sql
-- "I want to run in Davao City on Saturday morning at 8am"
SELECT 
  parameter,
  ROUND(forecast_value, 2) as value,
  ROUND(prediction_interval_lower, 2) as lower,
  ROUND(prediction_interval_upper, 2) as upper,
  CASE 
    WHEN parameter = 'precipitation' THEN 
      CASE WHEN forecast_value < 1 THEN '✅ Light' 
           WHEN forecast_value < 5 THEN '⚠️ Moderate'
           ELSE '❌ Heavy' END
    WHEN parameter = 'temperature' THEN
      CASE WHEN forecast_value < 25 THEN '✅ Cool'
           WHEN forecast_value < 30 THEN '⚠️ Warm'
           ELSE '❌ Hot' END
    WHEN parameter = 'humidity' THEN
      CASE WHEN forecast_value < 70 THEN '✅ Comfortable'
           WHEN forecast_value < 85 THEN '⚠️ Humid'
           ELSE '❌ Very Humid' END
    ELSE 'OK'
  END as assessment
FROM `your-project.weather.forecast_results`
WHERE lat = 7.07  -- Davao City
  AND EXTRACT(DAYOFWEEK FROM forecast_timestamp) = 7  -- Saturday
  AND EXTRACT(HOUR FROM forecast_timestamp) = 8  -- 8 AM
  AND forecast_timestamp >= CURRENT_TIMESTAMP()
ORDER BY parameter;
```

---

## 🔄 Pipeline Summary

### Complete Execution Flow

```
Step 0: Configuration (10 minutes - manual)
  ↓
Step 1: Fetch Data (10 minutes - automated)
  → Output: gs://bucket/weather_data_hourly.parquet
  ↓
Step 2: Load to BigQuery (2 minutes - automated)
  → Output: weather.weather_data table
  ↓
Step 3: Train Models (60-120 minutes - automated)
  → Output: 6 ARIMA models
  ↓
Step 4: Generate Forecasts (10 minutes - automated)
  → Output: weather.forecast_results table
  ↓
Step 5: Validation (5 minutes - manual)
  → Verify: All data and models correct
```

**Total time:** ~90-150 minutes (1.5-2.5 hours)

### BigQuery Resources Created

| Resource | Name | Type | Size |
|----------|------|------|------|
| Dataset | `weather` | Dataset | - |
| Table | `weather.weather_data` | Raw data | ~15 MB |
| Model | `weather.precipitation_arima` | ARIMA_PLUS | - |
| Model | `weather.temperature_arima` | ARIMA_PLUS | - |
| Model | `weather.wind_arima` | ARIMA_PLUS | - |
| Model | `weather.humidity_arima` | ARIMA_PLUS | - |
| Model | `weather.solar_arima` | ARIMA_PLUS | - |
| Model | `weather.cloud_arima` | ARIMA_PLUS | - |
| Table | `weather.forecast_results` | Forecast | ~1-2 MB |

---

## 🚨 Troubleshooting

### Issue: API rate limiting
```
Error: 429 Too Many Requests from NASA POWER API
```
**Solution:** Wait 5-10 minutes, then retry Step 1

### Issue: BigQuery quota exceeded
```
Error: Exceeded rate limits: too many concurrent training jobs
```
**Solution:** Use sequential training (Option A in Step 3)

### Issue: Model training fails
```
Error: Not enough data for ARIMA training
```
**Solution:** 
1. Check Step 2 completed: `bq show project:weather.weather_data`
2. Verify data has 3 years: Run validation query
3. Check for NULL values: `SELECT COUNT(*) FROM ... WHERE precipitation_mm IS NULL`

### Issue: Forecast table has wrong row count
```
Expected: 10,080 rows
Actual: Different number
```
**Solution:**
1. Check all 6 models exist: `bq ls project:weather | grep arima`
2. Verify each model trained successfully
3. Re-run Step 4 (forecast generation)

---

## 📝 Notes for AI Agents

1. **Sequential execution required:** Steps must be run in order (1 → 2 → 3 → 4)
2. **Step 3 is longest:** 60-120 minutes for model training
3. **Verify after each step:** Use validation queries before proceeding
4. **Idempotent operations:** All steps can be re-run safely (they use CREATE OR REPLACE)
5. **GCP authentication:** Ensure valid credentials before starting
6. **Error handling:** If any step fails, check logs and retry that step

---

## 🎯 Success Criteria

Pipeline is successful when:
- ✅ `weather.weather_data` has ~131,400 rows (5 locations × 3 years × 8760 hours)
- ✅ 6 ARIMA models exist in BigQuery
- ✅ `weather.forecast_results` has 10,080 rows (5 locations × 6 params × 336 hours)
- ✅ All validation queries return expected results
- ✅ Sample forecasts show reasonable values (no NULLs, no extreme outliers)

---

## 📚 Additional Resources

- **NASA POWER API Docs:** https://power.larc.nasa.gov/docs/
- **BigQuery ML ARIMA:** https://cloud.google.com/bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-time-series
- **Project Repository:** `/Users/kyle/Desktop/pixel-planet-101/`

---

**End of Pipeline Execution Guide**

