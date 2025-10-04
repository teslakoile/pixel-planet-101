"""
Fetch hourly weather data from NASA POWER API and save to Parquet
Supports multiple parameters (precipitation, temperature, etc.)
Replaces Steps 1-3 (manifest, transfer, zarr conversion) with direct API call
"""
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import gcsfs
from datetime import datetime
from typing import List, Dict
from pixel_planet.config import (
    POWER_API_BASE, PARAMETERS, FETCH_PARAMETERS, PRIMARY_PARAMETER, START_DATE, END_DATE,
    PARQUET_OUT, LOCATIONS
)

# ============================================================================
# FUNCTIONS
# ============================================================================

def fetch_power_data(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    parameters: List[str]
) -> dict:
    """
    Fetch hourly data from NASA POWER API for a single point.
    Can fetch multiple parameters in one API call.
    
    Args:
        lat: Latitude
        lon: Longitude
        start_date: Start date (YYYY-MM-DD format)
        end_date: End date (YYYY-MM-DD format)
        parameters: List of parameter names (e.g., ['PRECTOTCORR', 'T2M'])
        
    Returns:
        API response as dictionary
    """
    # Format dates for API (YYYYMMDD)
    start_str = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y%m%d")
    end_str = datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y%m%d")
    
    # Join multiple parameters with comma
    params_str = ','.join(parameters)
    
    # Build API URL
    url = (
        f"{POWER_API_BASE}"
        f"?parameters={params_str}"
        f"&community=RE"  # Renewable Energy community
        f"&longitude={lon}"
        f"&latitude={lat}"
        f"&start={start_str}"
        f"&end={end_str}"
        f"&format=JSON"
    )
    
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    
    data = response.json()
    return data


def fetch_specific_locations(
    locations: dict,
    start_date: str,
    end_date: str,
    parameters: List[str]
) -> pd.DataFrame:
    """
    Fetch data for specific locations (not a grid).
    
    Args:
        locations: Dict of location configs with lat/lon
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        parameters: List of NASA POWER parameters
        
    Returns:
        DataFrame with columns: ts, lat, lon, location_name, [parameter columns]
    """
    all_data = []
    
    for location_id, location_info in locations.items():
        lat = location_info['lat']
        lon = location_info['lon']
        name = location_info['name']
        
        print(f"\n📍 Fetching: {name}")
        print(f"   Coordinates: ({lat:.2f}, {lon:.2f})")
        
        try:
            data = fetch_power_data(lat, lon, start_date, end_date, parameters)
            
            if 'properties' in data and 'parameter' in data['properties']:
                param_dict = data['properties']['parameter']
                
                # Build dataframe from first parameter
                first_param = parameters[0]
                df_point = pd.DataFrame(
                    list(param_dict[first_param].items()), 
                    columns=['timestamp', first_param]
                )
                
                # Merge other parameters
                for param in parameters[1:]:
                    if param in param_dict:
                        df_param = pd.DataFrame(
                            list(param_dict[param].items()), 
                            columns=['timestamp', param]
                        )
                        df_point = df_point.merge(df_param, on='timestamp', how='left')
                
                df_point['lat'] = lat
                df_point['lon'] = lon
                df_point['location_name'] = name
                all_data.append(df_point)
                
                print(f"   ✓ Retrieved {len(df_point):,} hourly records")
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data fetched from API")
    
    # Combine all locations
    df_all = pd.concat(all_data, ignore_index=True)
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'], format='%Y%m%d%H')
    
    # Rename columns
    from pixel_planet.config import PARAMETERS
    rename_map = {'timestamp': 'ts'}
    for param in parameters:
        column_name = PARAMETERS.get(param, f'{param}_value')
        rename_map[param] = column_name
    
    df_all = df_all.rename(columns=rename_map)
    df_all = df_all.sort_values(['location_name', 'ts']).reset_index(drop=True)
    df_all['ts'] = pd.to_datetime(df_all['ts']).dt.tz_localize('UTC')
    
    return df_all


def write_parquet_to_gcs(df: pd.DataFrame, gcs_path: str) -> None:
    """
    Write pandas DataFrame to Parquet file in GCS.
    """
    data_columns = [col for col in df.columns if col not in ['ts', 'lat', 'lon', 'location_name']]
    
    schema_fields = [
        pa.field('ts', pa.timestamp('us', tz='UTC')),
        pa.field('lat', pa.float64()),
        pa.field('lon', pa.float64()),
        pa.field('location_name', pa.string()),
    ]
    for col in data_columns:
        schema_fields.append(pa.field(col, pa.float64()))
    
    schema = pa.schema(schema_fields)
    df = df[['ts', 'lat', 'lon', 'location_name'] + data_columns]
    table = pa.Table.from_pandas(df, schema=schema)
    
    fs = gcsfs.GCSFileSystem()
    with fs.open(gcs_path, "wb") as f:
        pq.write_table(table, f, compression="snappy")


def main():
    """Main execution function."""
    print("="*70)
    print("NASA POWER API - Multi-Location Data Fetch")
    print("="*70)
    print(f"Start date: {START_DATE}")
    print(f"End date: {END_DATE}")
    print(f"Locations: {len(LOCATIONS)}")
    print(f"Parameters: {len(FETCH_PARAMETERS)}")
    print()
    
    df = fetch_specific_locations(
        locations=LOCATIONS,
        start_date=START_DATE,
        end_date=END_DATE,
        parameters=FETCH_PARAMETERS
    )
    
    print(f"\n{'='*70}")
    print(f"📊 Data Summary:")
    print(f"   Total records: {len(df):,}")
    print(f"   Locations: {df['location_name'].nunique()}")
    print(f"   Date range: {df['ts'].min()} to {df['ts'].max()}")
    print(f"   Parameters: {len(FETCH_PARAMETERS)}")
    print(f"{'='*70}\n")
    
    print(f"💾 Writing to GCS: {PARQUET_OUT}")
    write_parquet_to_gcs(df, PARQUET_OUT)
    print(f"✅ Upload complete!\n")


if __name__ == "__main__":
    main()
