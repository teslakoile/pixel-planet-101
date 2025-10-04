"""
Step 5: Train BigQuery ML ARIMA_PLUS model
Supports training models for any of the 6 core weather parameters
Uses ARIMA_PLUS for time-series forecasting with uncertainty bounds
"""
from google.cloud import bigquery
import time
import argparse
from pixel_planet.config import (
    PROJECT_ID, BQ_DATASET, BQ_TABLE, BQ_MODEL,
    HORIZON, CONFIDENCE_LEVEL, BQ_TABLE_FULL_ID, BQ_MODEL_FULL_ID,
    ML_MODELS, BQ_MODELS
)

# ============================================================================
# FUNCTIONS
# ============================================================================

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
    
    This model type:
    - Supports spatial features (lat, lon) via TIME_SERIES_ID_COL
    - Provides uncertainty bounds (prediction intervals)
    - AUTO_ARIMA automatically selects best ARIMA parameters
    - Training time: 10-20 minutes per model
    
    Args:
        client: BigQuery client
        project_id: GCP project ID
        dataset_id: Dataset name
        model_id: Model name
        table_id: Source table (project.dataset.table)
        horizon: Forecast horizon (number of time steps)
        target_column: Target column name (e.g., 'precipitation_mm'). If None, uses PRIMARY_PARAMETER
        
    Returns:
        Completed query job
    """
    model_full_id = f"{project_id}.{dataset_id}.{model_id}"
    
    # Get target column if not provided
    if target_column is None:
        from pixel_planet.config import PARAMETERS, PRIMARY_PARAMETER
        target_column = PARAMETERS[PRIMARY_PARAMETER]
    
    print(f"Creating model: {model_full_id}")
    print(f"  Model type: ARIMA_PLUS")
    print(f"  Target column: {target_column}")
    print(f"  Horizon: {horizon} hours ({horizon/24:.1f} days)")
    print(f"  Spatial features: lat, lon (TIME_SERIES_ID_COL)")
    print(f"  ⏰ Training time: 10-20 minutes")
    
    # BQML CREATE MODEL SQL - ARIMA_PLUS for spatial time-series
    # Note: lat/lon must be CAST to STRING for TIME_SERIES_ID_COL
    create_model_sql = f"""
    CREATE OR REPLACE MODEL `{model_full_id}`
    OPTIONS(
      MODEL_TYPE = 'ARIMA_PLUS',
      TIME_SERIES_TIMESTAMP_COL = 'ts',
      TIME_SERIES_DATA_COL = '{target_column}',
      TIME_SERIES_ID_COL = ['lat_str', 'lon_str'],
      HORIZON = {horizon},
      AUTO_ARIMA = TRUE,
      DATA_FREQUENCY = 'HOURLY'
    ) AS
    SELECT 
      ts,
      CAST(lat AS STRING) AS lat_str,
      CAST(lon AS STRING) AS lon_str,
      {target_column}
    FROM `{table_id}`
    WHERE ts >= TIMESTAMP('2022-01-01')
      AND {target_column} IS NOT NULL
    ORDER BY lat, lon, ts
    """
    
    print("\n🚀 Starting ARIMA_PLUS training...")
    print("   This will take 10-20 minutes.")
    print("   You can monitor progress in the BigQuery console:")
    print(f"   https://console.cloud.google.com/bigquery?project={project_id}&p={project_id}&d={dataset_id}&t={model_id}&page=model")
    
    query_job = client.query(create_model_sql)
    
    print("\n   Job submitted. Waiting for completion...")
    # Wait for completion (10-20 minutes)
    query_job.result()
    
    print(f"\n✓ Model trained successfully!")
    return query_job


def evaluate_model(
    client: bigquery.Client,
    model_id: str
) -> None:
    """
    Evaluate model training metrics.
    
    Args:
        client: BigQuery client
        model_id: Fully-qualified model ID
    """
    print(f"\n{'='*70}")
    print("Model Evaluation Metrics")
    print(f"{'='*70}\n")
    
    eval_query = f"""
    SELECT *
    FROM ML.EVALUATE(MODEL `{model_id}`)
    """
    
    results = client.query(eval_query).result()
    
    for row in results:
        print(f"Metrics for model: {model_id}")
        for key, value in row.items():
            print(f"  {key}: {value}")


def generate_forecast(
    client: bigquery.Client,
    model_id: str,
    table_id: str,
    horizon: int,
    confidence_level: float,
    limit: int = 10
) -> None:
    """
    Generate sample forecast to verify model works.
    
    Args:
        client: BigQuery client
        model_id: Fully-qualified model ID
        table_id: Source table ID
        horizon: Forecast horizon
        confidence_level: Confidence level for intervals
        limit: Number of rows to display
    """
    print(f"\n{'='*70}")
    print(f"Sample Forecast (first {limit} rows)")
    print(f"{'='*70}\n")
    
    forecast_query = f"""
    SELECT
      lat_str,
      lon_str,
      forecast_timestamp,
      forecast_value,
      standard_error,
      confidence_level,
      prediction_interval_lower_bound,
      prediction_interval_upper_bound,
      confidence_interval_lower_bound,
      confidence_interval_upper_bound
    FROM ML.FORECAST(
      MODEL `{model_id}`,
      STRUCT(
        {horizon} AS horizon,
        {confidence_level} AS confidence_level
      )
    )
    ORDER BY lat_str, lon_str, forecast_timestamp
    LIMIT {limit}
    """
    
    results = client.query(forecast_query).result()
    
    print(f"{'Lat':<10} {'Lon':<10} {'Timestamp':<20} {'Forecast':<10} {'Lower':<10} {'Upper':<10}")
    print("-" * 70)
    
    for row in results:
        print(f"{row.lat_str:<10} {row.lon_str:<10} {str(row.forecast_timestamp):<20} "
              f"{row.forecast_value:<10.2f} {row.prediction_interval_lower_bound:<10.2f} "
              f"{row.prediction_interval_upper_bound:<10.2f}")


def main():
    """Main execution function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Train ARIMA_PLUS model for weather parameter forecasting'
    )
    parser.add_argument(
        '--target',
        type=str,
        default='precipitation',
        choices=list(ML_MODELS.keys()),
        help='Which parameter to forecast (default: precipitation)'
    )
    args = parser.parse_args()
    
    # Get model configuration
    model_config = ML_MODELS[args.target]
    model_name = model_config['model_name']
    target_column = model_config['column']
    model_full_id = f"{PROJECT_ID}.{BQ_DATASET}.{model_name}"
    
    print(f"\n{'='*70}")
    print(f"TRAINING MODEL: {args.target.upper()}")
    print(f"{'='*70}")
    print(f"Target: {args.target}")
    print(f"Model name: {model_name}")
    print(f"Target column: {target_column}")
    print(f"Model ID: {model_full_id}\n")
    
    client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Train ARIMA_PLUS model
    create_arima_model(
        client=client,
        project_id=PROJECT_ID,
        dataset_id=BQ_DATASET,
        model_id=model_name,
        table_id=BQ_TABLE_FULL_ID,
        horizon=HORIZON,
        target_column=target_column
    )
    
    # Step 2: Evaluate model
    evaluate_model(client, model_full_id)
    
    # Step 3: Generate sample forecast
    generate_forecast(
        client=client,
        model_id=model_full_id,
        table_id=BQ_TABLE_FULL_ID,
        horizon=HORIZON,
        confidence_level=CONFIDENCE_LEVEL,
        limit=10
    )
    
    print(f"\n{'='*70}")
    print("✓ Model Training Complete!")
    print(f"{'='*70}\n")
    print(f"Model: {model_full_id}")
    print(f"Next steps:")
    print(f"  1. Generate batch forecast: python -m pixel_planet.batch_forecast --model {args.target}")
    print(f"  2. Query forecasts in BigQuery")
    print(f"  3. Visualize results in notebooks")


if __name__ == "__main__":
    main()
