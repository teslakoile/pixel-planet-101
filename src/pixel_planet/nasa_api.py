"""
NASA POWER API client for fetching weather data
"""
import requests


def get_precipitation_data(latitude, longitude, start_date, end_date):
    """
    Fetch precipitation data from NASA POWER API
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        start_date: Start date in format YYYYMMDD
        end_date: End date in format YYYYMMDD
        
    Returns:
        dict: JSON response from NASA POWER API
    """
    base_url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "PRECTOTCORR",
        "community": "AG",
        "longitude": str(longitude),
        "latitude": str(latitude),
        "start": start_date,
        "end": end_date,
        "time-standard": "UTC",
        "format": "JSON"
    }
    
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    
    return response.json()

