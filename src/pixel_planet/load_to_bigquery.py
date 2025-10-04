"""
Step 4: Load Parquet from GCS to BigQuery table
"""
from google.cloud import bigquery
import time
from pixel_planet.config import (
    PROJECT_ID, DEST_BUCKET, PARQUET_OUT,
    BQ_DATASET, BQ_TABLE, BQ_LOCATION
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def create_dataset_if_not_exists(
    client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    location: str
) -> None:
    """
    Create BigQuery dataset if it doesn't exist.
    
    Args:
        client: BigQuery client
        project_id: GCP project ID
        dataset_id: Dataset name
        location: BigQuery location (US, EU, etc.)
    """
    dataset_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    dataset_ref.location = location
    
    try:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"✓ Dataset {dataset_id} ready")
    except Exception as e:
        print(f"Error creating dataset: {e}")
        raise


def load_parquet_to_bq(
    client: bigquery.Client,
    source_uri: str,
    table_id: str
) -> bigquery.LoadJob:
    """
    Load Parquet file from GCS to BigQuery table.
    
    Args:
        client: BigQuery client
        source_uri: GCS URI (gs://bucket/path/file.parquet)
        table_id: Fully-qualified table ID (project.dataset.table)
        
    Returns:
        Completed LoadJob
    """
    print(f"Loading {source_uri} → {table_id}")
    
    # Define explicit schema (autodetect doesn't always work with timestamps)
    # Schema supports multiple weather parameters and locations
    from pixel_planet.config import PARAMETERS
    
    schema = [
        bigquery.SchemaField("ts", "TIMESTAMP", mode="NULLABLE"),
        bigquery.SchemaField("lat", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("lon", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("location_name", "STRING", mode="NULLABLE"),
    ]
    
    # Add parameter columns dynamically
    for param_name, column_name in PARAMETERS.items():
        schema.append(bigquery.SchemaField(column_name, "FLOAT64", mode="NULLABLE"))
    
    # Configure load job
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        schema=schema,
        # Overwrite table if exists
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
    )
    
    # Start load job
    load_job = client.load_table_from_uri(
        source_uri,
        table_id,
        job_config=job_config
    )
    
    print(f"Job started: {load_job.job_id}")
    
    # Wait for completion
    print("Waiting for job to complete...")
    load_job.result()  # Blocks until done
    
    print(f"✓ Load job complete")
    return load_job


def validate_table(client: bigquery.Client, table_id: str) -> None:
    """
    Print table metadata for validation.
    
    Args:
        client: BigQuery client
        table_id: Fully-qualified table ID
    """
    table = client.get_table(table_id)
    
    print(f"\n✓ Table: {table_id}")
    print(f"  Rows: {table.num_rows:,}")
    print(f"  Size: {table.num_bytes / 1024 / 1024:.2f} MB")
    print(f"  Created: {table.created}")
    print(f"  Modified: {table.modified}")
    
    print(f"\n  Schema:")
    for field in table.schema:
        print(f"    - {field.name}: {field.field_type} (mode: {field.mode})")


def preview_data(client: bigquery.Client, table_id: str, limit: int = 5) -> None:
    """
    Query and print sample rows.
    
    Args:
        client: BigQuery client
        table_id: Fully-qualified table ID
        limit: Number of rows to preview
    """
    query = f"""
    SELECT *
    FROM `{table_id}`
    ORDER BY ts
    LIMIT {limit}
    """
    
    print(f"\n  Preview (first {limit} rows):")
    results = client.query(query).result()
    
    for row in results:
        print(f"    {dict(row)}")


def main():
    """Main execution function."""
    # Initialize BigQuery client
    client = bigquery.Client(project=PROJECT_ID)
    
    # Step 1: Ensure dataset exists
    create_dataset_if_not_exists(client, PROJECT_ID, BQ_DATASET, BQ_LOCATION)
    
    # Step 2: Load Parquet to BigQuery
    table_id = f"{PROJECT_ID}.{BQ_DATASET}.{BQ_TABLE}"
    load_job = load_parquet_to_bq(client, PARQUET_OUT, table_id)
    
    # Step 3: Validate table
    validate_table(client, table_id)
    
    # Step 4: Preview data
    preview_data(client, table_id, limit=5)
    
    print("\n✓ Step 4 Complete: Data loaded to BigQuery")
    print(f"  Table: {table_id}")


if __name__ == "__main__":
    main()
