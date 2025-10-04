"""
Example Python code for calling the Pixel Planet Weather Agent API

This script demonstrates how to interact with the deployed API using the requests library.
"""

import requests
import json
from typing import Dict, Any


# Your deployed API URL
API_BASE_URL = "https://pixel-planet-api-eixw6uscdq-uc.a.run.app"


def check_health() -> Dict[str, Any]:
    """
    Check if the API is healthy and running.
    
    Returns:
        dict: Health status response
    """
    url = f"{API_BASE_URL}/health"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def assess_activity(
    location_name: str,
    latitude: float,
    longitude: float,
    start_time: str,
    end_time: str,
    activity_type: str
) -> Dict[str, Any]:
    """
    Get AI-powered activity assessment with weather forecasts.
    
    Args:
        location_name: Name of the location (e.g., "Mt. Apo")
        latitude: Latitude in decimal degrees (-90 to 90)
        longitude: Longitude in decimal degrees (-180 to 180)
        start_time: Start time in ISO format (e.g., "2025-10-04T05:00:00")
        end_time: End time in ISO format
        activity_type: Type of activity (e.g., "hiking", "beach", "cycling")
        
    Returns:
        dict: Complete assessment with AI reasoning, forecasts, and chart data
    """
    url = f"{API_BASE_URL}/api/v1/assess-activity"
    
    payload = {
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "start_time": start_time,
        "end_time": end_time,
        "activity_type": activity_type
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def get_forecast_data(
    location_name: str,
    latitude: float,
    longitude: float,
    start_time: str,
    end_time: str
) -> Dict[str, Any]:
    """
    Get raw forecast data without AI analysis.
    
    Args:
        location_name: Name of the location
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees
        start_time: Start time in ISO format
        end_time: End time in ISO format
        
    Returns:
        dict: Raw forecast data with all parameters
    """
    url = f"{API_BASE_URL}/api/v1/forecast-data"
    
    payload = {
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "start_time": start_time,
        "end_time": end_time
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json()


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Pixel Planet Weather Agent API - Python Examples")
    print("=" * 70)
    
    # Example 1: Health Check
    print("\n1️⃣ Health Check")
    print("-" * 70)
    try:
        health = check_health()
        print(f"✅ API Status: {health['status']}")
        print(f"   Agent Initialized: {health['agent_initialized']}")
        print(f"   Project: {health['project_id']}")
        print(f"   Model: {health['model']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 2: Activity Assessment (Mt. Apo Hiking)
    print("\n2️⃣ Activity Assessment - Mt. Apo Hiking")
    print("-" * 70)
    try:
        result = assess_activity(
            location_name="Mt. Apo",
            latitude=6.987,
            longitude=125.273,
            start_time="2025-10-04T05:00:00",
            end_time="2025-10-05T21:00:00",
            activity_type="hiking"
        )
        
        # Print AI assessment
        assessment = result['assessment']
        print(f"\n🤖 AI Assessment:")
        print(f"   Suitable: {assessment['suitable']}")
        print(f"   Risk Level: {assessment['risk_level']}")
        
        if assessment.get('concerns'):
            print(f"\n⚠️  Concerns:")
            for concern in assessment['concerns']:
                print(f"   • {concern}")
        
        if assessment.get('recommendations'):
            print(f"\n💡 Recommendations:")
            for rec in assessment['recommendations']:
                print(f"   • {rec}")
        
        # Print forecast summary
        print(f"\n📊 Forecast Summary:")
        for param, stats in result['forecast_summary'].items():
            print(f"   {param.title()}: {stats['min']:.1f} - {stats['max']:.1f} (avg: {stats['avg']:.1f})")
        
        # Print location info
        location = result['location']
        print(f"\n📍 Location Info:")
        print(f"   Name: {location['name']}")
        print(f"   Coordinates: {location['coordinates']}")
        print(f"   Interpolation: {location['interpolation_used']}")
        print(f"   Confidence: {location['confidence']}")
        
        # Chart data is available in result['chart_data']
        print(f"\n📈 Chart Data Available:")
        for param, data_points in result['chart_data'].items():
            print(f"   {param}: {len(data_points)} time points")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 3: Beach Activity in Boracay
    print("\n3️⃣ Activity Assessment - Boracay Beach Day")
    print("-" * 70)
    try:
        result = assess_activity(
            location_name="Boracay",
            latitude=11.967,
            longitude=121.925,
            start_time="2025-10-05T08:00:00",
            end_time="2025-10-05T18:00:00",
            activity_type="beach day"
        )
        
        assessment = result['assessment']
        print(f"   Suitable: {assessment['suitable']}")
        print(f"   Risk Level: {assessment['risk_level']}")
        
        if assessment.get('alternative_times'):
            print(f"\n🔄 Alternative Times Suggested:")
            for alt in assessment['alternative_times']:
                print(f"   • {alt}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Example 4: Raw Forecast Data (No AI)
    print("\n4️⃣ Raw Forecast Data - Davao City")
    print("-" * 70)
    try:
        result = get_forecast_data(
            location_name="Davao City",
            latitude=7.07,
            longitude=125.61,
            start_time="2025-10-04T00:00:00",
            end_time="2025-10-04T23:00:00"
        )
        
        print(f"   Location: {result['location']['name']}")
        print(f"   Total Records: {result['total_records']}")
        print(f"\n   Available Parameters:")
        for param in result['forecasts'].keys():
            print(f"   • {param}: {len(result['forecasts'][param])} time points")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Examples complete!")
    print("=" * 70)


# =============================================================================
# USAGE IN YOUR OWN CODE
# =============================================================================

"""
QUICK START - Copy this into your code:

import requests

# 1. Check API health
response = requests.get("https://pixel-planet-api-eixw6uscdq-uc.a.run.app/health")
print(response.json())

# 2. Assess activity safety
response = requests.post(
    "https://pixel-planet-api-eixw6uscdq-uc.a.run.app/api/v1/assess-activity",
    json={
        "location_name": "Mt. Apo",
        "latitude": 6.987,
        "longitude": 125.273,
        "start_time": "2025-10-04T05:00:00",
        "end_time": "2025-10-05T21:00:00",
        "activity_type": "hiking"
    }
)
result = response.json()

# 3. Access the data
print(f"Suitable: {result['assessment']['suitable']}")
print(f"Risk: {result['assessment']['risk_level']}")

# 4. Use chart data for visualization
chart_data = result['chart_data']
for param, points in chart_data.items():
    # Each point has: timestamp, value, lower, upper
    print(f"{param}: {len(points)} data points")
"""

