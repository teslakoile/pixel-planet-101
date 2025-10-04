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

