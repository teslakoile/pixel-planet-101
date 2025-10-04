"""
Central configuration for NASA POWER → GCP pipeline
"""
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ============================================================================
# GCP Configuration
# ============================================================================
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project")
PROJECT_NUMBER = os.getenv("GCP_PROJECT_NUMBER", "YOUR_PROJECT_NUMBER")
REGION = os.getenv("GCP_REGION", "us-central1")
DEST_BUCKET = os.getenv("GCS_BUCKET", "your-gcs-bucket")

# ============================================================================
# Vertex AI Agent Configuration
# ============================================================================
VERTEX_AI_MODEL = os.getenv("VERTEX_AI_MODEL", "gemini-2.0-flash-exp")  # Gemini model with reasoning
VERTEX_AI_REGION = os.getenv("VERTEX_AI_REGION", REGION)  # Defaults to same as GCP_REGION

# ============================================================================
# NASA POWER API Configuration
# ============================================================================
POWER_API_BASE = "https://power.larc.nasa.gov/api/temporal/hourly/point"

# Available parameters from NASA POWER API
# Docs: https://power.larc.nasa.gov/docs/services/api/temporal/hourly/
AVAILABLE_PARAMETERS = {
    'PRECTOTCORR': 'precipitation_mm',           # Corrected precipitation (mm/hour)
    'T2M': 'temperature_2m_c',                   # Temperature at 2m (°C)
    'WS10M': 'windspeed_10m_ms',                 # Wind speed at 10m (m/s)
    'T2MDEW': 'dewpoint_2m_c',                   # Dew point at 2m (°C)
    'RH2M': 'humidity_2m_pct',                   # Relative humidity at 2m (%)
    'PS': 'surface_pressure_kpa',                # Surface pressure (kPa)
    'QV2M': 'specific_humidity_2m',              # Specific humidity at 2m (g/kg)
    'ALLSKY_SFC_SW_DWN': 'solar_radiation_wm2',  # Solar radiation (W/m²) - for UV exposure
    'CLOUD_AMT': 'cloud_cover_pct',              # Total cloud cover (%) - visibility/rain indicator
    # Note: NASA POWER does not have air quality data (PM2.5, AQI, etc.)
    # For air quality, consider: OpenAQ API, EPA AirNow, or Sentinel-5P satellite data
}

# Parameters to fetch - The 6 core parameters for comprehensive outdoor activity safety
# Each will get its own ML forecasting model
FETCH_PARAMETERS = [
    'PRECTOTCORR',       # 1. Precipitation - Rain detection
    'T2M',               # 2. Temperature - Heat/cold hazards
    'WS10M',             # 3. Wind speed - Wind hazards
    'RH2M',              # 4. Humidity - Heat index, comfort
    'ALLSKY_SFC_SW_DWN', # 5. Solar radiation - UV exposure
    'CLOUD_AMT',         # 6. Cloud cover - Visibility, sun protection
]

# ============================================================================
# ML Model Configuration - One ARIMA model per parameter
# ============================================================================
# Each parameter will have its own ARIMA_PLUS model trained
# This allows independent forecasting of each weather dimension
# ARIMA handles multiple locations via TIME_SERIES_ID_COL=['lat', 'lon']

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

# Primary target parameter for ML model (default if no --target specified)
PRIMARY_PARAMETER = "PRECTOTCORR"

# Create PARAMETERS dict with only fetched parameters
PARAMETERS = {k: AVAILABLE_PARAMETERS[k] for k in FETCH_PARAMETERS}

# ============================================================================
# GCS Path Structure (API approach - no S3 transfer needed)
# ============================================================================
# Generic path - can store multiple parameters
PARQUET_OUT = f"gs://{DEST_BUCKET}/processed/weather_data_hourly.parquet"

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

# Legacy grid parameters (kept for backward compatibility, not used)
LAT_MIN = float(os.getenv("LAT_MIN", "6.5"))
LAT_MAX = float(os.getenv("LAT_MAX", "8.0"))
LON_MIN = float(os.getenv("LON_MIN", "125.0"))
LON_MAX = float(os.getenv("LON_MAX", "126.5"))

# Time range - Rolling 3-year window (most recent complete data)
# Dynamically calculated: end = last day of previous month, start = 3 years before
def get_rolling_date_range(years_back: int = 3):
    """
    Calculate rolling date range for training data.
    
    Args:
        years_back: Number of years to go back from current date
        
    Returns:
        tuple: (start_date, end_date) as strings in 'YYYY-MM-DD' format
    """
    today = datetime.now()
    
    # Get last day of previous month (to ensure complete data)
    first_of_current_month = today.replace(day=1)
    end_of_last_month = first_of_current_month - timedelta(days=1)
    
    # Start date: first day of month, N years ago
    start = end_of_last_month - relativedelta(years=years_back)
    start = start.replace(day=1)
    
    return start.strftime('%Y-%m-%d'), end_of_last_month.strftime('%Y-%m-%d')

# Calculate dates (can be overridden by env vars)
_calculated_start, _calculated_end = get_rolling_date_range(years_back=3)
START_DATE = os.getenv("START_DATE", _calculated_start)
END_DATE = os.getenv("END_DATE", _calculated_end)

# ============================================================================
# BigQuery Configuration
# ============================================================================
BQ_DATASET = os.getenv("BQ_DATASET", "weather")
BQ_TABLE = os.getenv("BQ_TABLE", "weather_data")  # Generic table for all parameters
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")

# BigQuery model names (one ARIMA per parameter) - matches ML_MODELS configuration
BQ_MODELS = {
    'precipitation': os.getenv("BQ_MODEL_PRECIP", "precipitation_arima"),
    'temperature': os.getenv("BQ_MODEL_TEMP", "temperature_arima"),
    'wind': os.getenv("BQ_MODEL_WIND", "wind_arima"),
    'humidity': os.getenv("BQ_MODEL_HUMIDITY", "humidity_arima"),
    'solar_radiation': os.getenv("BQ_MODEL_UV", "solar_arima"),
    'cloud_cover': os.getenv("BQ_MODEL_CLOUD", "cloud_arima"),
}

# Primary model for initial implementation (default)
BQ_MODEL = BQ_MODELS['precipitation']

# ============================================================================
# BQML Model Configuration
# ============================================================================
HORIZON = int(os.getenv("BQML_HORIZON", "336"))  # 2 weeks = 336 hours
CONFIDENCE_LEVEL = float(os.getenv("CONFIDENCE_LEVEL", "0.90"))

# ============================================================================
# Derived Paths
# ============================================================================
BQ_TABLE_FULL_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
BQ_MODEL_FULL_ID = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_MODEL}"
