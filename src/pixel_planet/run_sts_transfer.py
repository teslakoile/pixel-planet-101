"""
Step 2: Run Storage Transfer Service job (URL list → GCS)
"""
from google.cloud import storage_transfer
from datetime import datetime
import time
from pixel_planet.config import (
    PROJECT_ID, DEST_BUCKET, MANIFEST_GCS_PATH, DEST_PREFIX
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def create_sts_job(
    project_id: str,
    manifest_url: str,
    dest_bucket: str,
    dest_prefix: str
) -> str:
    """
    Create a Storage Transfer Service job using HTTP data source.
    
    Args:
        project_id: GCP project ID
        manifest_url: GCS path to TSV manifest
        dest_bucket: Destination GCS bucket name
        dest_prefix: Destination path prefix within bucket
        
    Returns:
        Job name (format: transferJobs/...)
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    # Get today's date for schedule
    now = datetime.utcnow()
    
    # Build transfer job configuration
    transfer_job_config = storage_transfer.TransferJob(
        project_id=project_id,
        description="NASA POWER Zarr (URL list) → GCS mirror",
        status=storage_transfer.TransferJob.Status.ENABLED,
        
        # One-time schedule (start_date == end_date)
        schedule=storage_transfer.Schedule(
            schedule_start_date={
                "year": now.year,
                "month": now.month,
                "day": now.day
            },
            schedule_end_date={
                "year": now.year,
                "month": now.month,
                "day": now.day
            }
        ),
        
        # Transfer specification
        transfer_spec=storage_transfer.TransferSpec(
            # HTTP data source (URL list)
            http_data_source=storage_transfer.HttpData(
                list_url=manifest_url  # TSV manifest in GCS
            ),
            
            # GCS destination
            gcs_data_sink=storage_transfer.GcsData(
                bucket_name=dest_bucket,
                path=dest_prefix
            )
        )
    )
    
    # Create job
    print("Creating Storage Transfer Service job...")
    request = storage_transfer.CreateTransferJobRequest(
        transfer_job=transfer_job_config
    )
    
    response = client.create_transfer_job(request=request)
    job_name = response.name
    
    print(f"✓ Created job: {job_name}")
    return job_name


def run_sts_job(project_id: str, job_name: str) -> None:
    """
    Trigger immediate execution of STS job.
    
    Args:
        project_id: GCP project ID
        job_name: Job name from create_sts_job()
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    print("Triggering job run...")
    request = storage_transfer.RunTransferJobRequest(
        project_id=project_id,
        job_name=job_name
    )
    
    client.run_transfer_job(request=request)
    print(f"✓ Triggered run for: {job_name}")


def wait_for_job_completion(project_id: str, job_name: str, timeout_seconds: int = 3600) -> None:
    """
    Poll job status until completion or timeout.
    
    Args:
        project_id: GCP project ID
        job_name: Job name
        timeout_seconds: Maximum wait time (default 1 hour)
    """
    client = storage_transfer.StorageTransferServiceClient()
    
    print("\nMonitoring job status...")
    start_time = time.time()
    
    while True:
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            print(f"⚠ Timeout after {timeout_seconds} seconds")
            break
        
        # List operations for this job
        request = storage_transfer.ListTransferOperationsRequest(
            name="transferOperations",
            filter=f'{{"project_id": "{project_id}", "job_names": ["{job_name}"]}}'
        )
        
        operations = client.list_transfer_operations(request=request)
        
        # Check latest operation
        for op in operations:
            metadata = op.metadata
            
            if metadata:
                status = metadata.status
                print(f"Status: {status}, Transferred: {metadata.counters.bytes_copied_to_sink} bytes")
                
                if status == storage_transfer.TransferOperation.Status.SUCCESS:
                    print("\n✓ Transfer completed successfully!")
                    return
                    
                elif status == storage_transfer.TransferOperation.Status.FAILED:
                    print(f"\n✗ Transfer failed: {metadata.error_breakdowns}")
                    raise RuntimeError("STS job failed")
        
        # Wait before next check
        time.sleep(30)


def main():
    """Main execution function."""
    # Step 1: Create STS job
    job_name = create_sts_job(
        project_id=PROJECT_ID,
        manifest_url=MANIFEST_GCS_PATH,
        dest_bucket=DEST_BUCKET,
        dest_prefix=DEST_PREFIX
    )
    
    # Step 2: Trigger job run
    run_sts_job(PROJECT_ID, job_name)
    
    # Step 3: Wait for completion
    print("\nTransfer in progress (this may take 10-30 minutes)...")
    wait_for_job_completion(PROJECT_ID, job_name)
    
    print("\n✓ Step 2 Complete: Zarr store transferred to GCS")
    print(f"  Destination: gs://{DEST_BUCKET}/{DEST_PREFIX}")


if __name__ == "__main__":
    main()

