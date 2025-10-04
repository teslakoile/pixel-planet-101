"""
Generate unified forecast table for all 6 weather parameters
Creates a single table with UNION ALL of forecasts from all models
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
    
    Args:
        client: BigQuery client
        horizon: Forecast horizon in hours (default: 336 = 2 weeks)
        confidence_level: Confidence level for prediction intervals (default: 0.9)
        
    Returns:
        BigQuery Table object
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
          CAST(lat_str AS FLOAT64) AS lat,
          CAST(lon_str AS FLOAT64) AS lon,
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
    print()


if __name__ == "__main__":
    main()
