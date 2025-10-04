# DNN-Based Multi-Parameter Weather Forecasting Pipeline

## 🎯 Architecture Overview

### **Design Philosophy**
- **1 DNN model per weather parameter** (6 total)
- **Single model learns all spatial locations** (ts, lat, lon as features)
- **Point predictions** (no uncertainty bounds)
- **Scalable to any lat/lon** (not limited to training grid points)

---

## 📊 BigQuery Data Organization

```
Dataset: weather
│
├── 📁 Historical Data (1 table - all parameters)
│   └── weather_data
│       ├── ts (TIMESTAMP)           # Hourly timestamps
│       ├── lat (FLOAT64)            # Latitude (6.5° to 8.0°N)
│       ├── lon (FLOAT64)            # Longitude (125.0° to 126.5°E)
│       ├── precipitation_mm         # Hourly rainfall (mm/hour)
│       ├── temperature_2m_c         # Temperature at 2m (°C)
│       ├── windspeed_10m_ms         # Wind speed at 10m (m/s)
│       ├── humidity_2m_pct          # Relative humidity (%)
│       ├── solar_radiation_wm2      # Solar radiation (W/m²)
│       └── cloud_cover_pct          # Cloud cover (%)
│
├── 🤖 Models (6 DNN models)
│   ├── precipitation_dnn            # DNN_REGRESSOR
│   ├── temperature_dnn              # DNN_REGRESSOR
│   ├── wind_dnn                     # DNN_REGRESSOR
│   ├── humidity_dnn                 # DNN_REGRESSOR
│   ├── solar_dnn                    # DNN_REGRESSOR
│   └── cloud_dnn                    # DNN_REGRESSOR
│
└── 📈 Forecast Results (6 tables - 1 per parameter)
    ├── precipitation_forecast
    │   ├── forecast_timestamp
    │   ├── lat
    │   ├── lon
    │   ├── forecast_value
    │   ├── forecast_date
    │   ├── forecast_hour
    │   ├── day_of_week
    │   └── day_name
    ├── temperature_forecast
    ├── wind_forecast
    ├── humidity_forecast
    ├── solar_forecast
    └── cloud_forecast
```

---

## 🧠 DNN Model Architecture

### **Model Type: DNN_REGRESSOR**

#### Input Features (Feature Engineering)
```sql
-- Temporal features
UNIX_SECONDS(ts) AS ts_unix,
EXTRACT(HOUR FROM ts) AS hour_of_day,        -- 0-23
EXTRACT(DAYOFWEEK FROM ts) AS day_of_week,   -- 1-7
EXTRACT(DAYOFYEAR FROM ts) AS day_of_year,   -- 1-365
EXTRACT(MONTH FROM ts) AS month,             -- 1-12

-- Spatial features
lat,    -- 6.5 to 8.0
lon     -- 125.0 to 126.5
```

#### Network Architecture
```python
HIDDEN_UNITS = [128, 64, 32]  # 3 hidden layers
ACTIVATION_FN = 'RELU'
DROPOUT = 0.2
BATCH_SIZE = 64
LEARN_RATE = 0.001
MAX_ITERATIONS = 50
EARLY_STOP = TRUE
```

#### Output
- **Single value:** Predicted weather parameter value
- **No uncertainty bounds** (point prediction only)

---

## 🚀 Pipeline Execution

### **Step 1: Fetch Historical Data**
```bash
# Fetch 3 years of hourly data for all 6 parameters
python -m pixel_planet.fetch_power_api
```
- **Source:** NASA POWER API
- **Parameters:** PRECTOTCORR, T2M, WS10M, RH2M, ALLSKY_SFC_SW_DWN, CLOUD_AMT
- **Grid:** 16 points (4x4 grid over Davao Region)
- **Output:** `gs://your-bucket/processed/weather_data_hourly.parquet`

### **Step 2: Load to BigQuery**
```bash
python -m pixel_planet.load_to_bigquery
```
- **Table:** `weather.weather_data`
- **Schema:** ts, lat, lon, [6 parameter columns]

### **Step 3: Train DNN Models (6 separate training runs)**
```bash
# Train each parameter's model independently
python -m pixel_planet.train_bqml_model --target precipitation
python -m pixel_planet.train_bqml_model --target temperature
python -m pixel_planet.train_bqml_model --target wind
python -m pixel_planet.train_bqml_model --target humidity
python -m pixel_planet.train_bqml_model --target solar_radiation
python -m pixel_planet.train_bqml_model --target cloud_cover
```
- **Duration:** ~10-30 minutes per model
- **Output:** 6 trained DNN models in BigQuery

### **Step 4: Generate Batch Forecasts (6 separate forecast runs)**
```bash
# Generate 2-week forecasts for each parameter
python -m pixel_planet.batch_forecast --model precipitation
python -m pixel_planet.batch_forecast --model temperature
python -m pixel_planet.batch_forecast --model wind
python -m pixel_planet.batch_forecast --model humidity
python -m pixel_planet.batch_forecast --model solar_radiation
python -m pixel_planet.batch_forecast --model cloud_cover
```
- **Horizon:** 336 hours (14 days)
- **Output:** 6 forecast tables (one per parameter)

---

## 🔍 How DNN Handles Spatial-Temporal Data

### **Single Model Architecture**
```
Input: (ts, lat, lon)
         ↓
[Feature Engineering]
  • ts → hour, day, month, day_of_year
  • lat, lon → coordinates
         ↓
[DNN Layers: 128 → 64 → 32]
  • Learns spatial patterns (lat × lon interactions)
  • Learns temporal patterns (hour, day, season)
  • Learns location-specific behaviors
         ↓
Output: Predicted value for that (ts, lat, lon)
```

### **Advantages**
✅ **Spatial learning** - Model learns relationships between locations  
✅ **Scalable** - Can predict for ANY lat/lon (not just training grid)  
✅ **Interpolation** - Can forecast between grid points  
✅ **Efficient** - 1 model for all locations (vs 96 ARIMA models)  
✅ **Feature cross** - DNN learns lat × lon × time interactions  

### **Trade-offs**
❌ **No uncertainty bounds** - Only point predictions  
❌ **Black box** - Less interpretable than ARIMA  
❌ **Needs more data** - DNN requires larger training sets  

---

## 📋 Quick Reference: Model Training Status

| Parameter | Model Name | Target Column | Status |
|-----------|-----------|---------------|--------|
| Precipitation | `precipitation_dnn` | `precipitation_mm` | ⏳ Ready |
| Temperature | `temperature_dnn` | `temperature_2m_c` | ⏳ Ready |
| Wind Speed | `wind_dnn` | `windspeed_10m_ms` | ⏳ Ready |
| Humidity | `humidity_dnn` | `humidity_2m_pct` | ⏳ Ready |
| Solar Radiation | `solar_dnn` | `solar_radiation_wm2` | ⏳ Ready |
| Cloud Cover | `cloud_dnn` | `cloud_cover_pct` | ⏳ Ready |

---

## 🎯 Use Case: "Will It Rain on My Parade?"

### User Query
```
"I want to go running at 8am on Saturday, 4 days from now.
Location: Davao City (7.07°N, 125.61°E)"
```

### System Response (from 6 models)
```python
{
  "precipitation": {
    "value": 1.2,  # mm/hour
    "interpretation": "Light rain expected"
  },
  "temperature": {
    "value": 28.5,  # °C
    "interpretation": "Warm conditions"
  },
  "humidity": {
    "value": 82,  # %
    "interpretation": "High humidity - uncomfortable"
  },
  "wind": {
    "value": 3.2,  # m/s
    "interpretation": "Light breeze"
  },
  "solar_radiation": {
    "value": 150,  # W/m²
    "interpretation": "Low UV - cloudy"
  },
  "cloud_cover": {
    "value": 75,  # %
    "interpretation": "Mostly cloudy"
  },
  
  # Combined recommendation (application layer - future work)
  "recommendation": "⚠️ Not ideal for running",
  "hazards": ["Light rain", "High humidity", "Heat discomfort"],
  "alternatives": ["Wait until 6am", "Move to covered track"]
}
```

---

## 🔄 Pipeline Automation Script

```bash
#!/bin/bash
# train_all_models.sh

set -e

echo "🚀 Training all 6 DNN models..."

MODELS=("precipitation" "temperature" "wind" "humidity" "solar_radiation" "cloud_cover")

for model in "${MODELS[@]}"; do
    echo ""
    echo "================================"
    echo "Training: $model"
    echo "================================"
    python -m pixel_planet.train_bqml_model --target "$model"
done

echo ""
echo "✅ All models trained successfully!"
```

```bash
#!/bin/bash
# forecast_all_parameters.sh

set -e

echo "📈 Generating forecasts for all 6 parameters..."

MODELS=("precipitation" "temperature" "wind" "humidity" "solar_radiation" "cloud_cover")

for model in "${MODELS[@]}"; do
    echo ""
    echo "================================"
    echo "Forecasting: $model"
    echo "================================"
    python -m pixel_planet.batch_forecast --model "$model"
done

echo ""
echo "✅ All forecasts generated successfully!"
```

---

## 📊 Forecast Table Schema (All Parameters)

Each forecast table follows this structure:

```sql
CREATE TABLE weather.{parameter}_forecast (
  forecast_timestamp TIMESTAMP,   -- When prediction is for
  lat FLOAT64,                     -- Latitude
  lon FLOAT64,                     -- Longitude
  forecast_value FLOAT64,          -- Predicted value
  forecast_date DATE,              -- Date part of timestamp
  forecast_hour INT64,             -- Hour (0-23)
  day_of_week INT64,               -- Day of week (1=Sun, 7=Sat)
  day_name STRING                  -- Day name (e.g. "Saturday")
);
```

---

## 🎯 Next Steps

1. ✅ **Train first model** (precipitation)
2. ⏳ **Validate predictions** against historical data
3. ⏳ **Train remaining 5 models** (automate with shell script)
4. ⏳ **Build application layer** (combine forecasts into recommendations)
5. ⏳ **Create visualization dashboard** (show all 6 parameters)
6. ⏳ **Deploy as API** (for mobile app integration)

---

## 💡 Why DNN Over ARIMA?

| Aspect | ARIMA | DNN |
|--------|-------|-----|
| **Models needed** | 96 (16 per param) | 6 (1 per param) |
| **Spatial learning** | ❌ None | ✅ Full |
| **Scalability** | ❌ Fixed grid | ✅ Any location |
| **Uncertainty** | ✅ Intervals | ❌ None |
| **Interpretability** | ✅ High | ❌ Low |
| **Training time** | 5-20 min/location | 10-30 min total |
| **Prediction speed** | Fast | Fast |

**Decision:** Use DNN for better spatial learning and scalability, accepting trade-off of no uncertainty bounds.

---

## 🚦 Status: Ready to Train

All scripts updated for DNN approach. Ready to execute Step 3.

