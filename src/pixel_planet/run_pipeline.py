"""
Full pipeline orchestration: S3 → GCS → Parquet → BigQuery → BQML
"""
import sys
from pixel_planet.build_manifest import main as build_manifest
from pixel_planet.run_sts_transfer import main as run_sts
from pixel_planet.zarr_to_parquet import main as zarr_to_parquet
from pixel_planet.load_to_bigquery import main as load_to_bq
from pixel_planet.train_bqml_model import main as train_model

def main():
    """Run all pipeline steps sequentially."""
    steps = [
        ("Step 1: Build TSV Manifest", build_manifest),
        ("Step 2: Transfer S3 → GCS", run_sts),
        ("Step 3: Zarr → Parquet", zarr_to_parquet),
        ("Step 4: Load to BigQuery", load_to_bq),
        ("Step 5: Train BQML Model", train_model)
    ]
    
    for i, (step_name, step_func) in enumerate(steps, 1):
        print(f"\n{'='*70}")
        print(f"EXECUTING: {step_name}")
        print(f"{'='*70}\n")
        
        try:
            step_func()
        except Exception as e:
            print(f"\n✗ {step_name} FAILED: {e}")
            sys.exit(1)
    
    print(f"\n{'='*70}")
    print("✓ PIPELINE COMPLETE")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()

