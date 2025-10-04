# Multi-Model Forecasting Pipeline

## 🎯 Overview

This system trains **6 independent ML models** - one for each weather parameter. Each model forecasts its specific parameter 2 weeks into the future, providing comprehensive coverage for outdoor activity planning.

---

## 📊 The 6 Core Parameters & Their Models

| # | Parameter | Model Name | What It Forecasts | Use Cases |
|---|-----------|------------|-------------------|-----------|
| 1️⃣ | **PRECTOTCORR** | `precipitation_forecaster` | Rain (mm/hour) | Rain detection, outdoor events, sports |
| 2️⃣ | **T2M** | `temperature_forecaster` | Temperature (°C) | Heat stroke, cold risk, activity planning |
| 3️⃣ | **WS10M** | `wind_forecaster` | Wind speed (m/s) | Wind hazards, cycling, outdoor stability |
| 4️⃣ | **RH2M** | `humidity_forecaster` | Humidity (%) | Heat index, comfort, visibility |
| 5️⃣ | **ALLSKY_SFC_SW_DWN** | `uv_forecaster` | Solar radiation (W/m²) | UV exposure, sunburn risk, sun protection |
| 6️⃣ | **CLOUD_AMT** | `cloud_forecaster` | Cloud cover (%) | Visibility, sun protection, rain precursor |

---

## 🏗️ Architecture

### Data Flow
```
NASA POWER API 
    ↓
[6 parameters fetched simultaneously]
    ↓
GCS Parquet Storage
(weather_data_hourly.parquet)
    ↓
BigQuery Table: weather.weather_data
(ts, lat, lon, precipitation_mm, temperature_2m_c, windspeed_10m_ms, 
 humidity_2m_pct, solar_radiation_wm2, cloud_cover_pct)
    ↓
[Train 6 separate AUTOML_FORECASTER models]
    ↓
6 BigQuery ML Models:
  1. weather.precipitation_forecaster
  2. weather.temperature_forecaster
  3. weather.wind_forecaster
  4. weather.humidity_forecaster
  5. weather.uv_forecaster
  6. weather.cloud_forecaster
    ↓
[Generate batch predictions from each model]
    ↓
6 Forecast Tables:
  1. weather.precipitation_forecast
  2. weather.temperature_forecast
  3. weather.wind_forecast
  4. weather.humidity_forecast
  5. weather.uv_forecast
  6. weather.cloud_forecast
```

---

## 🚀 Pipeline Execution

### Phase 1: Data Ingestion (Run Once)
```bash
# Fetch all 6 parameters from NASA POWER API and load to BigQuery
python -m pixel_planet.run_pipeline_api
```

**Output:**
- ✅ Parquet file: `gs://your-bucket/processed/weather_data_hourly.parquet`
- ✅ BigQuery table: `weather.weather_data` (420,480 rows with 9 columns)

---

### Phase 2: Model Training (Run 6 Times - One per Parameter)

#### Option A: Train Primary Model First (Recommended)
```bash
# 1. Train precipitation model (priority)
python -m pixel_planet.train_bqml_model
# Training time: 1-6 hours
# Output: weather.precipitation_forecaster
```

#### Option B: Train All 6 Models ✅ (NOW SUPPORTED)
Use the `--target` argument to train different parameter models:

```bash
# Train all 6 models
python -m pixel_planet.train_bqml_model --target precipitation
python -m pixel_planet.train_bqml_model --target temperature
python -m pixel_planet.train_bqml_model --target wind
python -m pixel_planet.train_bqml_model --target humidity
python -m pixel_planet.train_bqml_model --target solar_radiation
python -m pixel_planet.train_bqml_model --target cloud_cover
```

**Total Training Time:** 6-36 hours (if run sequentially)
**Parallel Training:** Can train multiple models simultaneously (faster)

---

### Phase 3: Batch Prediction (Run 6 Times - One per Model) ✅ (NOW SUPPORTED)

Generate 2-week forecasts from each model using the `--model` argument:

```bash
# Generate forecasts from all 6 models
python -m pixel_planet.batch_forecast --model precipitation
python -m pixel_planet.batch_forecast --model temperature
python -m pixel_planet.batch_forecast --model wind
python -m pixel_planet.batch_forecast --model humidity
python -m pixel_planet.batch_forecast --model solar_radiation
python -m pixel_planet.batch_forecast --model cloud_cover
```

**Output:** 6 forecast tables in BigQuery
- `weather.precipitation_forecast` (336 hours × 16 locations = 5,376 rows)
- `weather.temperature_forecast` (5,376 rows)
- `weather.wind_forecast` (5,376 rows)
- `weather.humidity_forecast` (5,376 rows)
- `weather.uv_forecast` (5,376 rows)
- `weather.cloud_forecast` (5,376 rows)

---

## ✅ Multi-Model Support Implemented

The scripts now fully support training and forecasting for all 6 parameters!

### 1. ✅ `train_bqml_model.py` - Multi-Target Support

**Usage:**
```bash
python -m pixel_planet.train_bqml_model --target <parameter>
```

**Available targets:**
- `precipitation` (default)
- `temperature`
- `wind`
- `humidity`
- `solar_radiation`
- `cloud_cover`

**Example:**
```bash
python -m pixel_planet.train_bqml_model --target temperature
```

### 2. ✅ `batch_forecast.py` - Multi-Model Support

**Usage:**
```bash
python -m pixel_planet.batch_forecast --model <parameter>
```

**Available models:**
- `precipitation` (default)
- `temperature`
- `wind`
- `humidity`
- `solar_radiation`
- `cloud_cover`

**Example:**
```bash
python -m pixel_planet.batch_forecast --model wind
```

### 3. ✅ Configuration Updates

`config.py` now includes:
- All 6 parameters in `FETCH_PARAMETERS`
- `ML_MODELS` dict with configurations for each parameter
- `BQ_MODELS` dict with BigQuery model names for each parameter

---

## 💾 BigQuery Schema

### Input Table: `weather.weather_data`
```sql
ts                    TIMESTAMP  -- UTC timestamp
lat                   FLOAT64    -- Latitude
lon                   FLOAT64    -- Longitude
precipitation_mm      FLOAT64    -- Precipitation (mm/hr)
temperature_2m_c      FLOAT64    -- Temperature (°C)
windspeed_10m_ms      FLOAT64    -- Wind speed (m/s)
humidity_2m_pct       FLOAT64    -- Humidity (%)
solar_radiation_wm2   FLOAT64    -- Solar radiation (W/m²)
cloud_cover_pct       FLOAT64    -- Cloud cover (%)
```

### Forecast Table Schema (Example: `precipitation_forecast`)
```sql
lat                                 FLOAT64
lon                                 FLOAT64
forecast_timestamp                  TIMESTAMP
forecast_value                      FLOAT64    -- Predicted precipitation
prediction_interval_lower_bound     FLOAT64    -- 90% confidence lower
prediction_interval_upper_bound     FLOAT64    -- 90% confidence upper
confidence_level                    FLOAT64    -- 0.90
standard_error                      FLOAT64
forecast_date                       DATE
forecast_hour                       INT64
day_of_week                         INT64
day_name                            STRING
interval_width                      FLOAT64
uncertainty_margin                  FLOAT64
```

---

## 🎯 Use Case Examples

### Example 1: "Will it rain during my 8-9am Saturday run?"
Query **precipitation_forecast** table:
```sql
SELECT 
  forecast_timestamp,
  forecast_value AS rain_mm_per_hour,
  prediction_interval_lower_bound,
  prediction_interval_upper_bound,
  CASE 
    WHEN forecast_value > 2.5 THEN 'HIGH_RAIN_RISK'
    WHEN forecast_value > 0.5 THEN 'LIGHT_RAIN_POSSIBLE'
    ELSE 'NO_RAIN_EXPECTED'
  END AS rain_risk
FROM `weather.precipitation_forecast`
WHERE 
  lat = 7.0 AND lon = 125.5  -- Davao City center
  AND EXTRACT(DAYOFWEEK FROM forecast_timestamp) = 7  -- Saturday
  AND EXTRACT(HOUR FROM forecast_timestamp) BETWEEN 8 AND 9
  AND DATE(forecast_timestamp) = '2025-10-11'  -- 4 days from now
ORDER BY forecast_timestamp
```

### Example 2: "Heat stroke risk for afternoon outdoor event?"
Query **temperature_forecast** + **humidity_forecast**:
```sql
WITH combined AS (
  SELECT 
    t.forecast_timestamp,
    t.forecast_value AS temperature_c,
    h.forecast_value AS humidity_pct,
    -- Heat Index calculation (simplified)
    t.forecast_value + (0.5 * h.forecast_value / 100 * (t.forecast_value - 14)) AS heat_index
  FROM `weather.temperature_forecast` t
  JOIN `weather.humidity_forecast` h
    ON t.forecast_timestamp = h.forecast_timestamp
    AND t.lat = h.lat AND t.lon = h.lon
  WHERE 
    t.lat = 7.0 AND t.lon = 125.5
    AND EXTRACT(HOUR FROM t.forecast_timestamp) BETWEEN 14 AND 17  -- 2-5pm
)
SELECT 
  forecast_timestamp,
  temperature_c,
  humidity_pct,
  heat_index,
  CASE
    WHEN heat_index > 41 THEN 'EXTREME_DANGER'
    WHEN heat_index > 39 THEN 'DANGER'
    WHEN heat_index > 32 THEN 'EXTREME_CAUTION'
    WHEN heat_index > 27 THEN 'CAUTION'
    ELSE 'SAFE'
  END AS heat_risk_level
FROM combined
ORDER BY forecast_timestamp
```

### Example 3: "Is it safe for cycling? (Wind + Rain + Temperature)"
Query all 3 relevant forecasts:
```sql
SELECT 
  p.forecast_timestamp,
  p.forecast_value AS rain_mm,
  t.forecast_value AS temp_c,
  w.forecast_value AS wind_ms,
  CASE 
    WHEN p.forecast_value > 1.0 THEN 'UNSAFE_RAIN'
    WHEN w.forecast_value > 12 THEN 'UNSAFE_WIND'
    WHEN t.forecast_value > 35 OR t.forecast_value < 15 THEN 'UNCOMFORTABLE_TEMP'
    ELSE 'SAFE_FOR_CYCLING'
  END AS cycling_recommendation
FROM `weather.precipitation_forecast` p
JOIN `weather.temperature_forecast` t
  ON p.forecast_timestamp = t.forecast_timestamp
  AND p.lat = t.lat AND p.lon = t.lon
JOIN `weather.wind_forecast` w
  ON p.forecast_timestamp = w.forecast_timestamp
  AND p.lat = w.lat AND p.lon = w.lon
WHERE p.lat = 7.0 AND p.lon = 125.5
ORDER BY p.forecast_timestamp
LIMIT 24  -- Next 24 hours
```

---

## ⚡ Quick Start (Step-by-Step)

```bash
# 1. Data ingestion (run once)
python -m pixel_planet.run_pipeline_api

# 2. Train primary model (precipitation)
python -m pixel_planet.train_bqml_model
# Wait 1-6 hours...

# 3. Generate batch predictions
python -m pixel_planet.batch_forecast

# 4. Query forecasts in BigQuery
bq query --use_legacy_sql=false \
  'SELECT * FROM `weather.precipitation_forecast` LIMIT 10'

# 5. (Optional) Train additional models
# Modify scripts to accept --target argument, then:
# python -m pixel_planet.train_bqml_model --target temperature
# python -m pixel_planet.batch_forecast --model temperature
# Repeat for other parameters...
```

---

## 📈 Benefits of Multi-Model Approach

✅ **Independent Forecasts**: Each parameter forecasted separately with its own uncertainty bounds  
✅ **Specialized Models**: Each model optimized for its specific target  
✅ **Flexible Queries**: Mix and match parameters for different use cases  
✅ **Incremental Development**: Train models one at a time, prioritize by importance  
✅ **Comprehensive Coverage**: 6 parameters cover all major outdoor activity hazards  
✅ **Scalable**: Easy to add more parameters/models later  

---

## 🎯 Roadmap

**Phase 1** (✅ COMPLETE): 
- ✅ Data pipeline setup
- ✅ Configuration for 6 parameters
- ✅ Multi-model training script
- ✅ Multi-model batch forecast script

**Phase 2** (CURRENT - Ready to Execute):
- 🔄 Run data ingestion (fetch all 6 parameters)
- 🔄 Train all 6 models (can run in parallel)
- 🔄 Generate batch predictions for all 6 parameters

**Phase 3** (NEXT):
- Build recommendation engine using all 6 forecasts
- Create API endpoint for activity recommendations
- Build web/mobile UI

---

**Storage Requirements:**
- Input data: ~30 MB (3 years × 6 parameters)
- Models: ~50-100 MB each (6 models = 300-600 MB)
- Forecasts: ~5 MB per forecast table (6 tables = 30 MB)
- **Total**: <1 GB in BigQuery

**Cost Estimate (Google Cloud):**
- Data ingestion: ~$0.01
- Model training: ~$3-5 per model × 6 = $18-30
- Batch predictions: ~$0.10 per model × 6 = $0.60
- **Total one-time setup**: ~$20-35
- **Monthly predictions**: ~$2-5 (if run daily)

