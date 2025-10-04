"""
Simplified pipeline using NASA POWER API (no S3 transfer needed)
Pipeline: API → Parquet → BigQuery → BQML
"""
import sys
from pixel_planet.fetch_power_api import main as fetch_api
from pixel_planet.load_to_bigquery import main as load_to_bq
from pixel_planet.train_bqml_model import main as train_model

def main():
    """Run simplified API-based pipeline."""
    steps = [
        ("Step 1: Fetch from NASA POWER API → Parquet", fetch_api),
        ("Step 2: Load to BigQuery", load_to_bq),
        ("Step 3: Train BQML Model", train_model)
    ]
    
    for i, (step_name, step_func) in enumerate(steps, 1):
        print(f"\n{'='*70}")
        print(f"EXECUTING: {step_name}")
        print(f"{'='*70}\n")
        
        try:
            step_func()
        except Exception as e:
            print(f"\n✗ {step_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    print(f"\n{'='*70}")
    print("✓ PIPELINE COMPLETE")
    print(f"{'='*70}")
    print("\nYou can now query your model:")
    print("  SELECT * FROM ML.FORECAST(")
    print("    MODEL `YOUR_PROJECT.weather.rain_arima`,")
    print("    STRUCT(336 AS horizon, 0.90 AS confidence_level)")
    print("  )")

if __name__ == "__main__":
    main()

