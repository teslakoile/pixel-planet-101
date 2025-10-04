"""
Step 1: Build TSV manifest of NASA POWER Zarr store URLs
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config
import gcsfs
from typing import List
from pixel_planet.config import (
    PROJECT_ID, DEST_BUCKET, ZARR_PREFIX, MANIFEST_GCS_PATH,
    S3_BUCKET, S3_REGION
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def list_s3_objects_public(bucket: str, prefix: str, region: str) -> List[str]:
    """
    List all objects in S3 bucket (uses .netrc for authentication if needed).
    
    Args:
        bucket: S3 bucket name
        prefix: Object key prefix to filter
        region: AWS region
        
    Returns:
        List of object keys
    """
    # Configure S3 client (will use .netrc credentials for GES DISC)
    # For public buckets, set AWS_NO_SIGN_REQUEST=YES environment variable
    s3_client = boto3.client("s3", region_name=region)
    
    object_keys = []
    paginator = s3_client.get_paginator("list_objects_v2")
    
    # Ensure prefix ends with /
    prefix_normalized = prefix.rstrip("/") + "/"
    
    print(f"Listing objects from s3://{bucket}/{prefix_normalized}")
    
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_normalized):
        if "Contents" not in page:
            continue
            
        for obj in page["Contents"]:
            object_keys.append(obj["Key"])
    
    print(f"Found {len(object_keys)} objects")
    return object_keys


def build_https_urls(bucket: str, keys: List[str], region: str) -> List[str]:
    """
    Convert S3 keys to HTTPS URLs.
    
    Args:
        bucket: S3 bucket name
        keys: List of S3 object keys
        region: AWS region
        
    Returns:
        List of HTTPS URLs
    """
    urls = []
    for key in keys:
        url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
        urls.append(url)
    return urls


def write_tsv_manifest(urls: List[str], gcs_path: str) -> None:
    """
    Write URL list to TSV file in GCS.
    
    STS requires:
    - Header: "TsvHttpData-1.0"
    - URLs must be lexicographically sorted
    - One URL per line
    
    Args:
        urls: List of HTTPS URLs
        gcs_path: GCS path (gs://bucket/path/file.tsv)
    """
    # Sort URLs (required by STS)
    urls_sorted = sorted(urls)
    
    # Write to GCS
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "w") as f:
        # Write TSV header
        f.write("TsvHttpData-1.0\n")
        
        # Write URLs
        for url in urls_sorted:
            f.write(url + "\n")
    
    print(f"Wrote manifest to {gcs_path}")
    print(f"Total URLs: {len(urls_sorted)}")


def main():
    """Main execution function."""
    # Step 1: List S3 objects
    object_keys = list_s3_objects_public(S3_BUCKET, ZARR_PREFIX, S3_REGION)
    
    if len(object_keys) == 0:
        raise ValueError(f"No objects found at s3://{S3_BUCKET}/{ZARR_PREFIX}")
    
    # Step 2: Build HTTPS URLs
    urls = build_https_urls(S3_BUCKET, object_keys, S3_REGION)
    
    # Step 3: Write TSV manifest to GCS
    write_tsv_manifest(urls, MANIFEST_GCS_PATH)
    
    print("\n✓ Step 1 Complete: TSV manifest created successfully")
    print(f"  Manifest location: {MANIFEST_GCS_PATH}")
    print(f"  Object count: {len(urls)}")


if __name__ == "__main__":
    main()

