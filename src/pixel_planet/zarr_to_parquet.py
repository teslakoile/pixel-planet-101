"""
Step 3: Read Zarr from GCS, subset, and write Parquet
"""
import fsspec
import xarray as xr
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gcsfs
from typing import Tuple
from pixel_planet.config import (
    DEST_BUCKET, DEST_PREFIX, VAR_NAME,
    START_DATE, END_DATE, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
    ZARR_GCS_URL, PARQUET_OUT
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def open_zarr_from_gcs(zarr_url: str) -> xr.Dataset:
    """
    Open Zarr store from GCS using fsspec mapper.
    
    Args:
        zarr_url: GCS URL (gs://bucket/path/store.zarr)
        
    Returns:
        xarray Dataset
    """
    print(f"Opening Zarr store: {zarr_url}")
    
    # Create fsspec mapper (gcsfs handles gs:// URLs)
    store = fsspec.get_mapper(zarr_url)
    
    # Open with xarray (consolidated=True for faster metadata access)
    ds = xr.open_zarr(store, consolidated=True)
    
    print(f"✓ Opened Zarr store")
    print(f"  Variables: {list(ds.data_vars)}")
    print(f"  Dimensions: {dict(ds.dims)}")
    print(f"  Coordinates: {list(ds.coords)}")
    
    return ds


def subset_data(
    ds: xr.Dataset,
    var_name: str,
    time_range: Tuple[str, str],
    lat_range: Tuple[float, float],
    lon_range: Tuple[float, float]
) -> xr.DataArray:
    """
    Subset dataset by variable, time, and spatial bounds.
    
    Args:
        ds: xarray Dataset
        var_name: Variable name to extract
        time_range: (start_date, end_date) as ISO strings
        lat_range: (lat_min, lat_max)
        lon_range: (lon_min, lon_max)
        
    Returns:
        xarray DataArray (subsetted)
    """
    print(f"\nSubsetting variable: {var_name}")
    print(f"  Time: {time_range[0]} to {time_range[1]}")
    print(f"  Latitude: {lat_range[0]} to {lat_range[1]}")
    print(f"  Longitude: {lon_range[0]} to {lon_range[1]}")
    
    # Extract variable
    da = ds[var_name]
    
    # Subset time
    da_sub = da.sel(time=slice(time_range[0], time_range[1]))
    
    # Subset lat/lon
    da_sub = da_sub.sel(
        lat=slice(lat_range[0], lat_range[1]),
        lon=slice(lon_range[0], lon_range[1])
    )
    
    # Load into memory (triggers actual data read from GCS)
    print("Loading data into memory...")
    da_sub = da_sub.load()
    
    print(f"✓ Subset complete")
    print(f"  Shape: {da_sub.shape}")
    print(f"  Size: {da_sub.nbytes / 1024 / 1024:.2f} MB")
    
    return da_sub


def aggregate_to_timeseries(da: xr.DataArray, var_name: str) -> pd.DataFrame:
    """
    Aggregate spatial dimensions (mean over lat/lon) to create time series.
    
    Args:
        da: xarray DataArray with dimensions (time, lat, lon)
        var_name: Variable name for column naming
        
    Returns:
        pandas DataFrame with columns [ts, {var_name}_mm]
    """
    print("\nAggregating spatial data (mean over grid cells)...")
    
    # Convert to DataFrame (long format)
    df = da.to_dataframe(name=f"{var_name}_mm").reset_index()
    
    # Group by time and take spatial mean
    df_agg = (
        df.groupby("time", as_index=False)[f"{var_name}_mm"]
        .mean()
        .rename(columns={"time": "ts"})
    )
    
    print(f"✓ Aggregation complete")
    print(f"  Rows: {len(df_agg)}")
    print(f"  Columns: {list(df_agg.columns)}")
    print(f"  Date range: {df_agg['ts'].min()} to {df_agg['ts'].max()}")
    
    return df_agg


def write_parquet_to_gcs(df: pd.DataFrame, gcs_path: str) -> None:
    """
    Write pandas DataFrame to Parquet file in GCS.
    
    Args:
        df: pandas DataFrame
        gcs_path: GCS destination path (gs://bucket/path/file.parquet)
    """
    print(f"\nWriting Parquet to: {gcs_path}")
    
    # Convert to PyArrow Table
    table = pa.Table.from_pandas(df)
    
    # Write to GCS
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")
    
    print(f"✓ Parquet file written")
    print(f"  Rows: {len(df)}")
    print(f"  Compression: snappy")


def main():
    """Main execution function."""
    # Step 1: Open Zarr from GCS
    ds = open_zarr_from_gcs(ZARR_GCS_URL)
    
    # Step 2: Subset data
    da_subset = subset_data(
        ds=ds,
        var_name=VAR_NAME,
        time_range=(START_DATE, END_DATE),
        lat_range=(LAT_MIN, LAT_MAX),
        lon_range=(LON_MIN, LON_MAX)
    )
    
    # Step 3: Aggregate to time series
    df = aggregate_to_timeseries(da_subset, VAR_NAME)
    
    # Step 4: Write Parquet
    write_parquet_to_gcs(df, PARQUET_OUT)
    
    print("\n✓ Step 3 Complete: Parquet file created")
    print(f"  Location: {PARQUET_OUT}")
    print(f"  Schema: ts (TIMESTAMP), {VAR_NAME}_mm (FLOAT64)")


if __name__ == "__main__":
    main()

