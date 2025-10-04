"""
Batch Forecast: Generate 2-week predictions and save to BigQuery table
Supports generating forecasts from any of the 6 weather parameter DNN models
Uses ML.PREDICT with future timestamps (no uncertainty bounds)
"""
from google.cloud import bigquery
import pandas as pd
from datetime import datetime, timedelta
import argparse
from pixel_planet.config import (
    PROJECT_ID, BQ_DATASET, BQ_MODEL_FULL_ID, HORIZON, CONFIDENCE_LEVEL,
    ML_MODELS, BQ_MODELS
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def generate_batch_forecast(
    client: bigquery.Client,
    model_id: str,
    horizon: int,
    confidence_level: float,
    output_table: str = None,
    target_column: str = "precipitation_mm"
) -> bigquery.Table:
    """
    Generate full horizon forecast and save to BigQuery table.
    
    For DNN models:
    - Uses ML.PREDICT with future timestamps
    - Generates forecasts for all (lat, lon) grid points
    - No uncertainty bounds (point predictions only)
    
    Args:
        client: BigQuery client
        model_id: Fully-qualified model ID
        horizon: Forecast horizon (hours)
        confidence_level: Not used for DNN (kept for compatibility)
        output_table: Output table ID. If None, uses default 'forecast_results'
        
    Returns:
        BigQuery Table object with forecast results
    """
    # Use default table if not specified
    if output_table is None:
        output_table = f"{PROJECT_ID}.{BQ_DATASET}.forecast_results"
    
    print(f"\n{'='*70}")
    print(f"Generating {horizon}-hour batch forecast ({horizon/24:.1f} days)")
    print(f"Model: {model_id}")
    print(f"Output table: {output_table}")
    print(f"Note: DNN produces point predictions (no uncertainty bounds)")
    print(f"{'='*70}\n")
    
    # Create forecast using ML.PREDICT with future timestamps
    # Strategy: Generate future timestamps for each grid point, then predict
    forecast_sql = f"""
    CREATE OR REPLACE TABLE `{output_table}` AS
    WITH 
    -- Get unique locations from training data
    locations AS (
      SELECT DISTINCT lat, lon
      FROM `{PROJECT_ID}.{BQ_DATASET}.weather_data`
    ),
    -- Get last timestamp from training data
    last_timestamp AS (
      SELECT MAX(ts) AS max_ts
      FROM `{PROJECT_ID}.{BQ_DATASET}.weather_data`
    ),
    -- Generate future hours (1 to horizon)
    future_hours AS (
      SELECT hour_offset
      FROM UNNEST(GENERATE_ARRAY(1, {horizon})) AS hour_offset
    ),
    -- Cross join to create future timestamps for each location
    future_data AS (
      SELECT
        l.lat,
        l.lon,
        TIMESTAMP_ADD(lt.max_ts, INTERVAL fh.hour_offset HOUR) AS forecast_timestamp
      FROM locations l
      CROSS JOIN last_timestamp lt
      CROSS JOIN future_hours fh
    ),
    -- Prepare features for DNN prediction
    prediction_input AS (
      SELECT
        lat,
        lon,
        forecast_timestamp,
        -- Temporal features (must match training features)
        UNIX_SECONDS(forecast_timestamp) AS ts_unix,
        EXTRACT(HOUR FROM forecast_timestamp) AS hour_of_day,
        EXTRACT(DAYOFWEEK FROM forecast_timestamp) AS day_of_week,
        EXTRACT(DAYOFYEAR FROM forecast_timestamp) AS day_of_year,
        EXTRACT(MONTH FROM forecast_timestamp) AS month
      FROM future_data
    )
    -- Generate predictions
    SELECT
      pi.lat,
      pi.lon,
      pi.forecast_timestamp,
      pred.predicted_{target_column} AS forecast_value,
      -- Add helpful time features
      EXTRACT(DATE FROM pi.forecast_timestamp) AS forecast_date,
      EXTRACT(HOUR FROM pi.forecast_timestamp) AS forecast_hour,
      EXTRACT(DAYOFWEEK FROM pi.forecast_timestamp) AS day_of_week,
      FORMAT_TIMESTAMP('%A', pi.forecast_timestamp) AS day_name
    FROM ML.PREDICT(
      MODEL `{model_id}`,
      (SELECT * FROM prediction_input)
    ) pred
    JOIN prediction_input pi
      ON pi.forecast_timestamp = pred.forecast_timestamp
      AND pi.lat = pred.lat
      AND pi.lon = pred.lon
    ORDER BY lat, lon, forecast_timestamp
    """
    
    print("Executing forecast query...")
    print("  Step 1: Generating future timestamps for all grid points")
    print("  Step 2: Preparing DNN input features")
    print("  Step 3: Running ML.PREDICT")
    query_job = client.query(forecast_sql)
    query_job.result()  # Wait for completion
    
    print(f"✓ Forecast complete and saved to: {output_table}")
    
    # Get table metadata
    table = client.get_table(output_table)
    print(f"  Rows: {table.num_rows:,}")
    print(f"  Size: {table.num_bytes / 1024:.2f} KB")
    print(f"  Grid points: {table.num_rows // horizon}")
    
    return table


def analyze_forecast(client: bigquery.Client, table_id: str) -> None:
    """
    Analyze and display forecast insights.
    
    Args:
        client: BigQuery client
        table_id: Forecast table ID
    """
    print(f"\n{'='*70}")
    print("FORECAST ANALYSIS")
    print(f"{'='*70}\n")
    
    # Get forecast summary (DNN version - no uncertainty bounds)
    summary_sql = f"""
    SELECT
      MIN(forecast_timestamp) AS start_time,
      MAX(forecast_timestamp) AS end_time,
      AVG(forecast_value) AS avg_value,
      MAX(forecast_value) AS max_value,
      MIN(forecast_value) AS min_value,
      STDDEV(forecast_value) AS stddev_value,
      COUNT(DISTINCT CONCAT(CAST(lat AS STRING), '_', CAST(lon AS STRING))) AS num_locations
    FROM `{table_id}`
    """
    
    result = list(client.query(summary_sql).result())[0]
    
    print("📊 Summary Statistics:")
    print(f"  Period: {result.start_time} to {result.end_time}")
    print(f"  Duration: {(result.end_time - result.start_time).total_seconds() / 3600:.0f} hours")
    print(f"  Grid locations: {result.num_locations}")
    print(f"  Avg value: {result.avg_value:.2f}")
    print(f"  Min value: {result.min_value:.2f}")
    print(f"  Max value: {result.max_value:.2f}")
    print(f"  Std deviation: {result.stddev_value:.2f}")
    print(f"\n  Note: DNN produces point predictions (no uncertainty bounds)")
    
    # Show daily averages
    print("\n📈 Daily Forecast Summary:")
    daily_sql = f"""
    WITH forecast_with_day AS (
      SELECT
        CAST(FLOOR(TIMESTAMP_DIFF(forecast_timestamp, MIN(forecast_timestamp) OVER(), HOUR) / 24) AS INT64) AS day_num,
        forecast_value
      FROM `{table_id}`
    )
    SELECT
      day_num,
      AVG(forecast_value) AS avg_value,
      MAX(forecast_value) AS max_value
    FROM forecast_with_day
    GROUP BY day_num
    ORDER BY day_num
    LIMIT 14
    """
    
    results = client.query(daily_sql).result()
    for row in results:
        bar_length = max(1, int(row.avg_value * 2))
        bar = '█' * bar_length
        print(f"  Day {row.day_num+1:2d}: avg={row.avg_value:5.2f}, max={row.max_value:5.2f} {bar}")
    
    # Show pertinent high-value dates
    print("\n⚠️  High Value Alerts (>5.0):")
    alerts_sql = f"""
    SELECT
      forecast_timestamp,
      day_name,
      lat,
      lon,
      forecast_value
    FROM `{table_id}`
    WHERE forecast_value > 5.0
    ORDER BY forecast_value DESC
    LIMIT 10
    """
    
    results = client.query(alerts_sql).result()
    alert_count = 0
    for row in results:
        alert_count += 1
        print(f"  {row.forecast_timestamp} ({row.day_name}):")
        print(f"    Location: ({row.lat:.2f}, {row.lon:.2f})")
        print(f"    Forecast: {row.forecast_value:.2f}")
    
    if alert_count == 0:
        print("  No significant rain events predicted (all <5mm/hour)")
    
    # Show daily summaries
    print("\n📅 Daily Totals:")
    daily_sql = f"""
    SELECT
      forecast_date,
      FORMAT_TIMESTAMP('%A, %B %d', MIN(forecast_timestamp)) AS date_display,
      AVG(forecast_value) AS avg_value,
      MAX(forecast_value) AS max_value
    FROM `{table_id}`
    GROUP BY forecast_date
    ORDER BY forecast_date
    """
    
    results = client.query(daily_sql).result()
    for row in results:
        print(f"  {row.date_display}: avg={row.avg_value:.2f}, max={row.max_value:.2f}")


def main():
    """Main execution function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Generate batch forecast for weather parameter'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='precipitation',
        choices=list(ML_MODELS.keys()),
        help='Which model to use for forecasting (default: precipitation)'
    )
    args = parser.parse_args()
    
    # Get model configuration
    model_config = ML_MODELS[args.model]
    model_name = BQ_MODELS[args.model]
    target_column = model_config['column']
    model_full_id = f"{PROJECT_ID}.{BQ_DATASET}.{model_name}"
    forecast_table = f"{PROJECT_ID}.{BQ_DATASET}.{args.model}_forecast"
    
    print(f"\n{'='*70}")
    print(f"BATCH FORECAST FOR: {args.model.upper()}")
    print(f"{'='*70}")
    print(f"Model: {model_name}")
    print(f"Model ID: {model_full_id}")
    print(f"Target column: {target_column}")
    print(f"Output table: {forecast_table}\n")
    
    client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Generate batch forecast
    table = generate_batch_forecast(
        client=client,
        model_id=model_full_id,
        horizon=HORIZON,
        confidence_level=CONFIDENCE_LEVEL,
        output_table=forecast_table,
        target_column=target_column
    )
    
    # Step 2: Analyze results
    analyze_forecast(client, forecast_table)
    
    print(f"\n{'='*70}")
    print("✓ BATCH FORECAST COMPLETE")
    print(f"{'='*70}")
    print(f"\n📊 Results saved to BigQuery table: {forecast_table}")
    print(f"\nQuery your forecasts:")
    print(f"  SELECT * FROM `{forecast_table}` ORDER BY forecast_timestamp")


if __name__ == "__main__":
    main()

