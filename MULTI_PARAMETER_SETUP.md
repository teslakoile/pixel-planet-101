# Multi-Parameter Weather Data Pipeline

## 📊 Configured Parameters

The pipeline now fetches **4 weather parameters** simultaneously:

| Parameter | NASA POWER Code | BigQuery Column | Description |
|-----------|----------------|-----------------|-------------|
| **Precipitation** | `PRECTOTCORR` | `precipitation_mm` | Corrected precipitation (mm/hour) |
| **Temperature** | `T2M` | `temperature_2m_c` | Temperature at 2 meters (°C) |
| **Wind Speed** | `WS10M` | `windspeed_10m_ms` | Wind speed at 10 meters (m/s) |
| **Humidity** | `RH2M` | `humidity_2m_pct` | Relative humidity at 2m (%) |

### ⚠️ Note on Air Quality
NASA POWER does not provide air quality data (PM2.5, AQI, etc.). 

**Alternative data sources for air quality:**
- **OpenAQ API**: Global air quality data from ground stations
- **EPA AirNow**: US air quality data
- **Sentinel-5P**: Satellite-based atmospheric composition data (NO2, O3, etc.)

We've included **Humidity (RH2M)** as a proxy since it correlates with some air quality factors.

## 🗄️ BigQuery Schema

### Table: `weather.weather_data`

```sql
ts                  TIMESTAMP  -- UTC timestamp (hourly)
lat                 FLOAT64    -- Latitude
lon                 FLOAT64    -- Longitude
precipitation_mm    FLOAT64    -- Precipitation (mm/hour)
temperature_2m_c    FLOAT64    -- Temperature (°C)
windspeed_10m_ms    FLOAT64    -- Wind speed (m/s)
humidity_2m_pct     FLOAT64    -- Relative humidity (%)
```

**Data structure**: Spatial panel data  
**Time range**: Rolling 3-year window (currently Oct 2022 - Sept 2025)  
**Spatial coverage**: Davao Region (6.5°N-8.0°N, 125.0°E-126.5°E)  
**Grid resolution**: 0.5° × 0.5° (16 locations)  
**Total rows**: ~420,480 (26,280 timestamps × 16 locations)

## 🤖 BQML Models

### Model: `weather.precipitation_forecaster`

- **Type**: AUTOML_FORECASTER
- **Target**: `precipitation_mm`
- **Features**: 
  - Temporal: `ts` (hourly timestamps)
  - Spatial: `lat`, `lon` (TIME_SERIES_ID_COL)
  - Could add: Other weather parameters as covariates
- **Horizon**: 336 hours (2 weeks)
- **Output**: Forecast with prediction intervals (uncertainty bounds)

### Future Models (expandable)

You can train additional models:

```python
# Temperature forecaster
BQ_MODEL = 'weather.temperature_forecaster'
TARGET_COLUMN = 'temperature_2m_c'

# Wind speed forecaster
BQ_MODEL = 'weather.wind_forecaster'
TARGET_COLUMN = 'windspeed_10m_ms'
```

## 📝 Configuration

### To modify parameters in `src/pixel_planet/config.py`:

```python
# Add/remove parameters to fetch
FETCH_PARAMETERS = [
    'PRECTOTCORR',  # Precipitation
    'T2M',          # Temperature
    'WS10M',        # Wind speed
    'RH2M',         # Humidity
    # Add more here
]

# Set primary target for ML model
PRIMARY_PARAMETER = "PRECTOTCORR"
```

### Available NASA POWER parameters:

```python
AVAILABLE_PARAMETERS = {
    'PRECTOTCORR': 'precipitation_mm',
    'T2M': 'temperature_2m_c',
    'WS10M': 'windspeed_10m_ms',
    'T2MDEW': 'dewpoint_2m_c',
    'RH2M': 'humidity_2m_pct',
    'PS': 'surface_pressure_kpa',
    'QV2M': 'specific_humidity_2m',
}
```

## 🚀 Running the Pipeline

```bash
# Activate environment
source .venv/bin/activate

# Install dependencies (if needed)
uv pip install -r requirements.txt

# Run full pipeline
python -m pixel_planet.run_pipeline_api
```

### Pipeline steps:
1. **Fetch**: Download 4 parameters from NASA POWER API (16 locations × 3 years)
2. **Load**: Upload Parquet to BigQuery table `weather.weather_data`
3. **Train**: Train AUTOML model on `precipitation_mm` (1-6 hours)

### Batch forecast:
```bash
python -m pixel_planet.batch_forecast
```

This generates 2-week forecasts for all 16 locations and saves to `weather.forecast_results`.

## 📈 Benefits of Multi-Parameter Setup

✅ **Richer features**: Can use temperature, wind, humidity as covariates for precipitation forecasting  
✅ **Multiple targets**: Train separate models for each parameter  
✅ **Better insights**: Understand relationships between weather variables  
✅ **Expandable**: Easy to add more parameters from NASA POWER  
✅ **Efficient**: All parameters fetched in single API call per location  

## 🎯 Next Steps

1. **Run the pipeline** to populate BigQuery with multi-parameter data
2. **Train the model** (initial: precipitation forecasting)
3. **Experiment with covariates**: Modify BQML SQL to include other weather parameters
4. **Train additional models**: Create forecasters for temperature, wind, etc.
5. **Integrate air quality**: Add external data source if needed

---

**Note**: The current model trains on `precipitation_mm` only. To use other parameters as features (covariates), modify the SQL in `train_bqml_model.py` to include additional columns in the SELECT statement.

