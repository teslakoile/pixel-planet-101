"""
Spatial utilities for weather forecast interpolation

Provides functions for:
- Distance calculation between coordinates
- Finding nearest forecast points
- Inverse Distance Weighting (IDW) interpolation
- Automatic handling of exact matches and edge cases
"""

import math
from typing import List, Dict, Any, Tuple, Optional


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in kilometers between two coordinates using Haversine formula.
    
    Args:
        lat1, lon1: First coordinate (decimal degrees)
        lat2, lon2: Second coordinate (decimal degrees)
        
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon1_rad = math.radians(lon1)
    lon2_rad = math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in kilometers
    r = 6371
    
    return c * r


def find_nearest_points(
    target_lat: float,
    target_lon: float,
    forecast_data: List[Dict],
    n_points: int = 3,
    distance_threshold: float = 0.01  # ~1km for exact match
) -> Tuple[List[Dict], bool]:
    """
    Find N nearest forecast points to target location.
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        forecast_data: List of forecast dictionaries with 'lat' and 'lon' keys
        n_points: Number of nearest points to return
        distance_threshold: Distance in km to consider exact match
        
    Returns:
        Tuple of (nearest_points, is_exact_match)
    """
    if not forecast_data:
        return [], False
    
    # Calculate distances and add to each record
    points_with_distance = []
    for record in forecast_data:
        distance = haversine_distance(
            target_lat, target_lon,
            record['lat'], record['lon']
        )
        record_copy = record.copy()
        record_copy['distance_km'] = distance
        points_with_distance.append(record_copy)
    
    # Sort by distance
    points_with_distance.sort(key=lambda x: x['distance_km'])
    
    # Check for exact match
    is_exact = points_with_distance[0]['distance_km'] < distance_threshold
    
    # Return top N points
    return points_with_distance[:n_points], is_exact


def inverse_distance_weighting(
    target_lat: float,
    target_lon: float,
    nearby_forecasts: List[Dict],
    power: float = 2.0
) -> Dict[str, Any]:
    """
    Interpolate forecast values using Inverse Distance Weighting (IDW).
    
    IDW formula: value = Σ(w_i * v_i) / Σ(w_i)
    where w_i = 1 / (distance_i ^ power)
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        nearby_forecasts: List of forecast records with 'lat', 'lon', 'forecast_value', etc.
        power: Power parameter for IDW (higher = more weight to closer points)
        
    Returns:
        Interpolated forecast record with weighted values
    """
    if not nearby_forecasts:
        return {}
    
    # If only one point, return it
    if len(nearby_forecasts) == 1:
        result = nearby_forecasts[0].copy()
        result['interpolation_method'] = 'nearest_point'
        return result
    
    # Calculate weights
    weights = []
    for record in nearby_forecasts:
        distance = record.get('distance_km')
        if distance is None:
            distance = haversine_distance(
                target_lat, target_lon,
                record['lat'], record['lon']
            )
        
        # Avoid division by zero for very close points
        if distance < 0.001:  # <1 meter
            # This is essentially exact match, return this point
            result = record.copy()
            result['interpolation_method'] = 'exact_match'
            return result
        
        weight = 1.0 / (distance ** power)
        weights.append(weight)
    
    total_weight = sum(weights)
    
    # Interpolate numeric fields
    interpolated = {
        'lat': target_lat,
        'lon': target_lon,
        'interpolation_method': 'idw',
        'n_points_used': len(nearby_forecasts),
        'distances_km': [r['distance_km'] for r in nearby_forecasts]
    }
    
    # Fields to interpolate
    numeric_fields = [
        'forecast_value',
        'prediction_interval_lower',
        'prediction_interval_upper',
        'standard_error',
        'confidence_level'
    ]
    
    for field in numeric_fields:
        if field in nearby_forecasts[0]:
            weighted_sum = sum(
                weights[i] * nearby_forecasts[i].get(field, 0)
                for i in range(len(nearby_forecasts))
            )
            interpolated[field] = weighted_sum / total_weight
    
    # Copy non-numeric fields from nearest point
    nearest = nearby_forecasts[0]
    for field in ['forecast_timestamp', 'parameter', 'forecast_date', 
                  'forecast_hour', 'day_of_week', 'day_name']:
        if field in nearest:
            interpolated[field] = nearest[field]
    
    return interpolated


def interpolate_forecast(
    target_lat: float,
    target_lon: float,
    all_forecasts: List[Dict],
    n_points: int = 3,
    max_interpolation_distance: float = 500.0
) -> Dict[str, Any]:
    """
    Main interpolation function that handles all cases automatically.
    
    Cases handled:
    1. Exact match (within ~1km): Return original data
    2. Within 200km: IDW interpolation from N nearest points
    3. 200-500km: Use nearest point only with warning
    4. >500km: Return warning about very low reliability
    5. No data: Return error
    
    Args:
        target_lat: Target latitude
        target_lon: Target longitude
        all_forecasts: All available forecast records
        n_points: Number of points to use for interpolation
        max_interpolation_distance: Maximum distance (km) for interpolation (default: 500km)
        
    Returns:
        Dict with:
        - success: Whether interpolation succeeded
        - interpolated_data: List of interpolated forecast records
        - metadata: Information about interpolation process
        - confidence: "high"/"medium"/"low"/"very_low" based on distances
        - warnings: List of warning messages if applicable
    """
    if not all_forecasts:
        return {
            'success': False,
            'error': 'No forecast data available',
            'interpolated_data': [],
            'metadata': {
                'interpolation_used': False,
                'confidence': 'none'
            }
        }
    
    # Group forecasts by timestamp and parameter
    grouped = {}
    for record in all_forecasts:
        key = (record['forecast_timestamp'], record['parameter'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(record)
    
    # Interpolate each group
    interpolated_results = []
    min_distance = float('inf')
    max_distance = 0
    interpolation_used = False
    
    for (timestamp, parameter), records in grouped.items():
        # Find nearest points for this timestamp/parameter combo
        nearest_points, is_exact = find_nearest_points(
            target_lat, target_lon, records, n_points
        )
        
        if not nearest_points:
            continue
        
        # Track distances
        distances = [p['distance_km'] for p in nearest_points]
        min_distance = min(min_distance, min(distances))
        max_distance = max(max_distance, max(distances))
        
        if is_exact:
            # Exact match - use as-is
            result = nearest_points[0].copy()
            result['interpolation_method'] = 'exact_match'
        else:
            # Interpolate
            interpolation_used = True
            result = inverse_distance_weighting(
                target_lat, target_lon, nearest_points
            )
        
        interpolated_results.append(result)
    
    # Determine confidence based on distances
    # Adjusted thresholds for sparse datasets (e.g., city-level data)
    if min_distance < 1:
        confidence = 'high'
    elif min_distance < 50:  # ~50km - same local region
        confidence = 'medium'
    elif min_distance < 200:  # ~200km - nearby region
        confidence = 'low'
    else:  # >200km - distant region
        confidence = 'very_low'
    
    metadata = {
        'interpolation_used': interpolation_used,
        'confidence': confidence,
        'nearest_distance_km': round(min_distance, 2),
        'furthest_distance_km': round(max_distance, 2),
        'n_points_used': n_points,
        'total_records_interpolated': len(interpolated_results)
    }
    
    # Generate warnings for problematic interpolations
    warnings = []
    if min_distance > max_interpolation_distance:
        warnings.append(
            f"EXTREME DISTANCE WARNING: Nearest data point is {min_distance:.0f}km away. "
            f"Forecast reliability is very limited at this distance. Consider this an "
            f"approximation only - local conditions may be vastly different."
        )
    elif min_distance > 300:
        warnings.append(
            f"Large distance warning: Interpolating from {min_distance:.0f}km away. "
            f"Weather patterns can vary significantly over this distance."
        )
    
    # If using multiple distant points, add spread warning
    if len(interpolated_results) > 0 and max_distance > 200 and (max_distance - min_distance) > 100:
        warnings.append(
            f"Data point spread: Interpolating from points ranging {min_distance:.0f}-{max_distance:.0f}km away. "
            f"Large spread may reduce interpolation accuracy."
        )
    
    return {
        'success': True,
        'interpolated_data': interpolated_results,
        'metadata': metadata,
        'warnings': warnings
    }


def get_location_confidence_message(metadata: Dict[str, Any]) -> str:
    """
    Generate human-readable message about interpolation confidence.
    
    Args:
        metadata: Interpolation metadata dict
        
    Returns:
        Confidence message string
    """
    if not metadata.get('interpolation_used'):
        return "Using exact location match from dataset."
    
    distance = metadata.get('nearest_distance_km', 0)
    confidence = metadata.get('confidence', 'unknown')
    
    messages = {
        'high': f"Forecast from exact or very close location match ({distance:.1f}km away). High confidence.",
        'medium': f"Forecast interpolated from locations {distance:.1f}km away within same region. Good confidence.",
        'low': f"Forecast interpolated from locations {distance:.1f}km away in nearby region. Moderate confidence - weather may vary locally.",
        'very_low': f"⚠️ Nearest forecast data is {distance:.1f}km away in distant region. Use with caution - local weather conditions may differ significantly."
    }
    
    return messages.get(confidence, f"Forecast from nearest location ({distance:.1f}km away).")

