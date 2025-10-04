"""
Vertex AI Gemini 2.5 Agent with BigQuery Tool Use POC

This demonstrates an AI agent that can:
1. Understand natural language questions about data
2. Generate and execute BigQuery SQL queries
3. Reason about results and provide insights
4. Handle follow-up questions with context

Requirements:
- google-cloud-aiplatform
- google-cloud-bigquery
- vertexai
"""

import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from collections import defaultdict

import vertexai
from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    ToolConfig,
    FunctionDeclaration,
    Part,
    Content
)
from google.cloud import bigquery
from google.cloud.bigquery import QueryJobConfig

# Import configuration from central config
from pixel_planet.config import (
    PROJECT_ID,
    REGION,
    BQ_DATASET,
    BQ_TABLE,
    BQ_TABLE_FULL_ID,
    VERTEX_AI_MODEL,
    VERTEX_AI_REGION
)

# Import spatial utilities
from pixel_planet.spatial_utils import (
    interpolate_forecast,
    get_location_confidence_message
)

# For backward compatibility
BQ_TABLE_FULL = BQ_TABLE_FULL_ID

# ============================================================================
# Utility Functions
# ============================================================================

def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from agent response.
    Handles markdown code blocks, mixed text/JSON responses, and various formats.
    
    Args:
        response_text: Raw text response from agent
        
    Returns:
        Parsed JSON dict, or dict with summary if no JSON found
    """
    # Try to find JSON in markdown code blocks (non-greedy match for nested braces)
    json_match = re.search(r'```json\s*(\{.*\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(1)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error in markdown block: {e}")
    
    # Try without markdown tags
    json_match = re.search(r'```\s*(\{.*\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            json_str = json_match.group(1)
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error in code block: {e}")
    
    # Try to find raw JSON (look for outermost braces)
    # Find the first { and last }
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')
    
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        potential_json = response_text[first_brace:last_brace+1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error in raw text: {e}")
    
    # Fallback: return text response with flag
    print(f"   ⚠️ Could not extract valid JSON from response")
    return {
        "summary": response_text,
        "raw_response": True,
        "parse_error": "Could not extract JSON from response"
    }


# ============================================================================
# BigQuery Tool Definition
# ============================================================================

def create_bigquery_tool() -> Tool:
    """
    Create a Vertex AI Tool with BigQuery query function.
    
    This allows the Gemini model to generate and execute SQL queries
    against BigQuery as part of its reasoning process.
    """
    
    query_bigquery_func = FunctionDeclaration(
        name="query_bigquery",
        description=(
            "Execute a SQL query against BigQuery weather forecast dataset. "
            "The table contains ML-generated hourly weather forecasts with the following schema:\n"
            "- forecast_timestamp (TIMESTAMP): The date/time the forecast is for (UTC)\n"
            "- lat (FLOAT): Latitude coordinate\n"
            "- lon (FLOAT): Longitude coordinate\n"
            "- parameter (STRING): Weather parameter - EXACTLY one of: 'precipitation', 'temperature', "
            "'wind', 'humidity', 'solar_radiation', 'cloud_cover'\n"
            "- forecast_value (FLOAT): Predicted value (WARNING: values near -999 indicate missing/invalid data)\n"
            "- prediction_interval_lower (FLOAT): Lower bound of 90% prediction interval\n"
            "- prediction_interval_upper (FLOAT): Upper bound of 90% prediction interval\n"
            "- confidence_level (FLOAT): Confidence level (typically 0.9)\n"
            "- standard_error (FLOAT): Standard error of prediction\n"
            "- forecast_date (DATE): Date portion of forecast\n"
            "- forecast_hour (INTEGER): Hour of day (0-23)\n"
            "- day_of_week (INTEGER): Day of week (1=Sunday, 2=Monday, ..., 7=Saturday)\n"
            "- day_name (STRING): Day name (Monday, Tuesday, etc.)\n"
            "IMPORTANT: Filter out invalid data with WHERE forecast_value > -500 (values around -999 are invalid).\n"
            "Use this to retrieve forecast data, compare parameters, analyze predictions, or check uncertainty."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sql_query": {
                    "type": "string",
                    "description": (
                        f"Valid BigQuery SQL query. Use table name: `{BQ_TABLE_FULL}`. "
                        "Include LIMIT clause to avoid large result sets (max 1000 rows). "
                        "Example: SELECT AVG(temperature_2m_c) as avg_temp FROM `{table}` "
                        "WHERE ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)"
                    )
                },
                "reason": {
                    "type": "string",
                    "description": "Explain why this query is needed and what insight it will provide"
                }
            },
            "required": ["sql_query", "reason"]
        }
    )
    
    get_schema_func = FunctionDeclaration(
        name="get_table_schema",
        description=(
            "Get the schema and metadata of the BigQuery weather forecast table. "
            "Use this to understand available columns, data types, table structure, "
            "and the date range of available forecasts."
        ),
        parameters={
            "type": "object",
            "properties": {},
            "required": []
        }
    )
    
    query_activity_forecast_func = FunctionDeclaration(
        name="query_activity_forecast",
        description=(
            "Query weather forecasts for a specific outdoor activity at a location and time range. "
            "Automatically handles spatial interpolation if exact coordinates not in dataset. "
            "Returns all 6 weather parameters with prediction intervals for the specified time period. "
            "Parameters available: 'precipitation', 'temperature', 'wind', 'humidity', 'solar_radiation', 'cloud_cover'. "
            "Automatically filters out invalid data (values around -999). "
            "Use this function FIRST for activity safety assessment - it returns structured forecast data."
        ),
        parameters={
            "type": "object",
            "properties": {
                "location_name": {
                    "type": "string",
                    "description": "Name of the location (e.g., 'Mt. Apo', 'Davao City Beach')"
                },
                "latitude": {
                    "type": "number",
                    "description": "Latitude coordinate (decimal degrees)"
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude coordinate (decimal degrees)"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO format (e.g., '2024-10-04T05:00:00') or SQL timestamp format"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO format or SQL timestamp format"
                },
                "activity_type": {
                    "type": "string",
                    "description": "Activity description (e.g., 'hiking', 'beach', 'outdoor event', 'cycling')"
                }
            },
            "required": ["latitude", "longitude", "start_time", "end_time", "activity_type"]
        }
    )
    
    # Create tool with all three functions
    bigquery_tool = Tool(
        function_declarations=[query_bigquery_func, get_schema_func, query_activity_forecast_func]
    )
    
    return bigquery_tool


# ============================================================================
# BigQuery Execution Functions
# ============================================================================

class BigQueryExecutor:
    """Handles actual BigQuery operations."""
    
    def __init__(self, project_id: str):
        # Initialize BigQuery client with explicit Standard SQL configuration
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id
        
        # Set default query job config to always use Standard SQL
        self.default_job_config = QueryJobConfig(use_legacy_sql=False)
    
    def query_bigquery(self, sql_query: str, reason: str = "") -> Dict[str, Any]:
        """
        Execute a SQL query and return results.
        
        Args:
            sql_query: SQL query string
            reason: Explanation of why this query is needed
            
        Returns:
            Dict with results, row count, and metadata
        """
        try:
            print(f"\n🔍 Executing query...")
            if reason:
                print(f"   Reason: {reason}")
            print(f"   SQL: {sql_query[:200]}{'...' if len(sql_query) > 200 else ''}")
            
            # Execute query with Standard SQL
            query_job = self.client.query(sql_query, job_config=self.default_job_config)
            results = query_job.result()
            
            # Convert to list of dicts
            rows = [dict(row) for row in results]
            
            # Convert datetime/date objects to strings for JSON serialization
            for row in rows:
                for key, value in row.items():
                    if isinstance(value, (datetime, date)):
                        row[key] = value.isoformat()
            
            # Calculate query time in milliseconds
            query_time_ms = 0
            if query_job.ended and query_job.started:
                query_time_ms = int((query_job.ended - query_job.started).total_seconds() * 1000)
            
            result = {
                "success": True,
                "row_count": len(rows),
                "rows": rows[:100],  # Limit to first 100 rows for response
                "total_rows": results.total_rows,
                "query_time_ms": query_time_ms
            }
            
            print(f"   ✓ Query returned {result['total_rows']} rows")
            return result
            
        except Exception as e:
            print(f"   ✗ Query error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def get_table_schema(self) -> Dict[str, Any]:
        """
        Get table schema and metadata.
        
        Returns:
            Dict with schema, row count, size, and sample data
        """
        try:
            table = self.client.get_table(BQ_TABLE_FULL)
            
            schema_info = {
                "success": True,
                "table_name": BQ_TABLE_FULL,
                "row_count": table.num_rows,
                "size_mb": round(table.num_bytes / 1024 / 1024, 2),
                "columns": [
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "mode": field.mode,
                        "description": field.description or ""
                    }
                    for field in table.schema
                ],
                "created": table.created.isoformat() if table.created else None,
                "modified": table.modified.isoformat() if table.modified else None
            }
            
            print(f"\n📊 Table Schema: {BQ_TABLE_FULL}")
            print(f"   Rows: {schema_info['row_count']:,}")
            print(f"   Columns: {len(schema_info['columns'])}")
            
            return schema_info
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def query_activity_forecast(
        self,
        latitude: float,
        longitude: float,
        start_time: str,
        end_time: str,
        activity_type: str,
        location_name: str = "Unknown"
    ) -> Dict[str, Any]:
        """
        Query forecasts for activity planning with automatic spatial interpolation.
        
        Args:
            latitude: Target latitude
            longitude: Target longitude
            start_time: Start timestamp (ISO format or SQL timestamp)
            end_time: End timestamp
            activity_type: Activity description
            location_name: Name of location (optional)
            
        Returns:
            Dict with structured forecast data ready for agent reasoning and charting
        """
        try:
            print(f"\n🎯 Querying activity forecast...")
            print(f"   Location: {location_name} ({latitude}, {longitude})")
            print(f"   Activity: {activity_type}")
            print(f"   Time: {start_time} to {end_time}")
            
            # Query all nearby forecasts with distance calculation
            # Use ST_DISTANCE for proper geography calculation and parameterized queries for safety
            sql_query = f"""
            WITH distances AS (
              SELECT 
                *,
                ST_DISTANCE(ST_GEOGPOINT(lon, lat), ST_GEOGPOINT(@lng, @lat)) / 1000 AS distance_km
              FROM `{BQ_TABLE_FULL}`
              WHERE forecast_timestamp BETWEEN @start_ts AND @end_ts
                AND forecast_value > -900  -- Filter out sentinel values (-999), keep everything else including negative temps
            )
            SELECT * FROM distances
            WHERE distance_km <= @radius_km
            ORDER BY distance_km, forecast_timestamp, parameter
            """
            
            # Configure query with parameters (safer and faster)
            job_config = QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("lat", "FLOAT64", latitude),
                    bigquery.ScalarQueryParameter("lng", "FLOAT64", longitude),
                    bigquery.ScalarQueryParameter("start_ts", "TIMESTAMP", start_time),
                    bigquery.ScalarQueryParameter("end_ts", "TIMESTAMP", end_time),
                    bigquery.ScalarQueryParameter("radius_km", "FLOAT64", 300),  # Wider radius for sparse grids
                ],
                use_legacy_sql=False,
            )
            
            # Execute query
            query_job = self.client.query(sql_query, job_config=job_config)
            results = query_job.result()
            
            # Check if we got any results (early exit for diagnostics)
            if results.total_rows == 0:
                print(f"   ✗ No rows found within 300km radius and time range")
                return {
                    "success": False,
                    "error": f"No forecast data found within 300km of ({latitude}, {longitude}) for time range {start_time} to {end_time}",
                    "location": {
                        "name": location_name,
                        "coordinates": {"lat": latitude, "lon": longitude}
                    },
                    "debug_info": {
                        "query_returned_rows": 0,
                        "search_radius_km": 300,
                        "suggestion": "Try a different location or time range"
                    }
                }
            
            # Convert to list of dicts
            all_forecasts = []
            for row in results:
                record = dict(row)
                # Convert datetime objects to ISO strings
                for key, value in record.items():
                    if isinstance(value, (datetime, date)):
                        record[key] = value.isoformat()
                all_forecasts.append(record)
            
            print(f"   ✓ Retrieved {len(all_forecasts)} nearby forecast records (within 300km)")
            
            if not all_forecasts:
                return {
                    "success": False,
                    "error": "No forecast data available for this location and time range",
                    "location": {
                        "name": location_name,
                        "coordinates": {"lat": latitude, "lon": longitude}
                    }
                }
            
            # Perform spatial interpolation
            print(f"   🔄 Performing spatial interpolation...")
            interpolation_result = interpolate_forecast(latitude, longitude, all_forecasts)
            
            if not interpolation_result['success']:
                return interpolation_result
            
            interpolated_data = interpolation_result['interpolated_data']
            metadata = interpolation_result['metadata']
            
            print(f"   ✓ Interpolation complete: {metadata['confidence']} confidence")
            print(f"   Distance to nearest data: {metadata['nearest_distance_km']}km")
            
            # Display warnings if any
            if 'warnings' in interpolation_result and interpolation_result['warnings']:
                print(f"\n   ⚠️ Interpolation Warnings:")
                for warning in interpolation_result['warnings']:
                    print(f"   {warning}")
            
            # Structure data by parameter for charting
            forecasts_by_parameter = defaultdict(list)
            
            for record in interpolated_data:
                param = record.get('parameter')
                if param:
                    forecasts_by_parameter[param].append({
                        'timestamp': record.get('forecast_timestamp'),
                        'value': record.get('forecast_value'),
                        'lower': record.get('prediction_interval_lower'),
                        'upper': record.get('prediction_interval_upper'),
                        'standard_error': record.get('standard_error')
                    })
            
            # Sort each parameter's forecasts by timestamp
            for param in forecasts_by_parameter:
                forecasts_by_parameter[param].sort(key=lambda x: x['timestamp'])
            
            # Calculate summary statistics for each parameter
            summary_stats = {}
            for param, forecasts in forecasts_by_parameter.items():
                values = [f['value'] for f in forecasts if f['value'] is not None]
                if values:
                    summary_stats[param] = {
                        'min': round(min(values), 2),
                        'max': round(max(values), 2),
                        'avg': round(sum(values) / len(values), 2),
                        'count': len(values)
                    }
            
            # Calculate duration
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                duration_hours = int((end_dt - start_dt).total_seconds() / 3600)
            except:
                duration_hours = None
            
            # Build structured response
            result = {
                "success": True,
                "location": {
                    "name": location_name,
                    "coordinates": {"lat": latitude, "lon": longitude},
                    "interpolation_used": metadata['interpolation_used'],
                    "nearest_distance_km": metadata['nearest_distance_km'],
                    "confidence": metadata['confidence'],
                    "confidence_message": get_location_confidence_message(metadata)
                },
                "time_range": {
                    "start": start_time,
                    "end": end_time,
                    "duration_hours": duration_hours
                },
                "activity": activity_type,
                "forecasts": dict(forecasts_by_parameter),
                "summary_stats": summary_stats,
                "total_records": len(interpolated_data)
            }
            
            print(f"   ✓ Structured {len(forecasts_by_parameter)} weather parameters")
            
            return result
            
        except Exception as e:
            print(f"   ✗ Error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "location": {
                    "name": location_name,
                    "coordinates": {"lat": latitude, "lon": longitude}
                }
            }
    
    def execute_function(self, function_name: str, function_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route function calls to appropriate methods.
        
        Args:
            function_name: Name of function to execute
            function_args: Arguments for the function
            
        Returns:
            Function execution results
        """
        if function_name == "query_bigquery":
            return self.query_bigquery(**function_args)
        elif function_name == "get_table_schema":
            return self.get_table_schema()
        elif function_name == "query_activity_forecast":
            return self.query_activity_forecast(**function_args)
        else:
            return {
                "success": False,
                "error": f"Unknown function: {function_name}"
            }


# ============================================================================
# Vertex AI Agent
# ============================================================================

class VertexAIAgent:
    """
    AI Agent using Gemini 2.5 with BigQuery reasoning capabilities.
    """
    
    def __init__(
        self,
        project_id: str = PROJECT_ID,
        region: str = VERTEX_AI_REGION,
        model_name: str = VERTEX_AI_MODEL
    ):
        """
        Initialize the agent.
        
        Args:
            project_id: GCP project ID (defaults to config.PROJECT_ID)
            region: GCP region for Vertex AI (defaults to config.VERTEX_AI_REGION)
            model_name: Gemini model to use (defaults to config.VERTEX_AI_MODEL)
        """
        self.project_id = project_id
        self.region = region
        
        # Storage for raw forecast data from tool calls (for charting)
        self._last_forecast_data = None
        
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=region)
        
        # Create BigQuery executor
        self.bq_executor = BigQueryExecutor(project_id)
        
        # Create model with tools
        self.bigquery_tool = create_bigquery_tool()
        
        # Create tool config to FORCE function calling (ANY mode)
        self.tool_config = ToolConfig(
            function_calling_config=ToolConfig.FunctionCallingConfig(
                mode=ToolConfig.FunctionCallingConfig.Mode.ANY,
                allowed_function_names=["query_activity_forecast"]
            )
        )
        
        self.model = GenerativeModel(
            model_name,
            tools=[self.bigquery_tool],
            system_instruction=[
                "You are an expert outdoor activity safety advisor with access to ML weather forecasts.",
                "",
                "YOUR ROLE:",
                "Assess outdoor activity safety based on weather forecasts and provide structured recommendations with complete forecast data for charting.",
                "",
                "TOOLS AVAILABLE:",
                "1. query_activity_forecast: Get weather forecasts for location/time/activity (USE THIS FIRST for activity assessments)",
                "2. query_bigquery: Run custom SQL queries if needed for additional analysis",
                "3. get_table_schema: Understand table structure",
                "",
                "WORKFLOW:",
                "1. Use query_activity_forecast to get forecast data for the requested activity",
                "2. Analyze all 6 weather parameters against safety thresholds",
                "3. Determine if conditions are suitable for the activity",
                "4. If unsuitable, find and recommend alternative time slots",
                "5. Return structured JSON output with assessment and complete forecast data",
                "",
                "SAFETY THRESHOLDS BY ACTIVITY:",
                "",
                "Hiking/Trekking/Mountain Activities:",
                "  - Temperature: CAUTION >32°C (heat exhaustion risk), UNSAFE >35°C; CAUTION <15°C, UNSAFE <10°C",
                "  - Precipitation: CAUTION >2mm/hr (slippery trails), UNSAFE >10mm/hr (flooding, landslides)",
                "  - Wind: CAUTION >15m/s (difficulty walking), UNSAFE >20m/s (dangerous at elevation)",
                "  - Humidity: CAUTION >75% with high temp (heat stress), prefer 40-70%",
                "  - Solar radiation: CAUTION >800W/m² (high UV), UNSAFE >1000W/m² (extreme UV)",
                "  - Cloud cover: <20% means high sun exposure, 30-70% is ideal",
                "",
                "Beach/Water Activities:",
                "  - Temperature: OPTIMAL 25-32°C, CAUTION <20°C or >35°C",
                "  - Precipitation: AVOID >1mm/hr (comfort), UNSAFE >5mm/hr (storms/lightning)",
                "  - Wind: CAUTION >10m/s (rough waves), UNSAFE >15m/s (dangerous conditions)",
                "  - Humidity: Less critical, but >85% feels oppressive",
                "  - Solar radiation: CAUTION >700W/m² (sunburn risk), use sun protection >500W/m²",
                "  - Cloud cover: <30% means intense sun exposure",
                "",
                "Outdoor Events/Picnics/Gatherings:",
                "  - Temperature: COMFORT 20-30°C, CAUTION <18°C or >33°C",
                "  - Precipitation: AVOID >0.5mm/hr (want to stay dry), CANCEL >2mm/hr",
                "  - Wind: CAUTION >12m/s (tent/equipment stability issues)",
                "  - Humidity: 40-70% is comfortable",
                "  - Cloud cover: 30-70% is ideal (shade without rain)",
                "",
                "Cycling/Running/Endurance Activities:",
                "  - Temperature: OPTIMAL 15-25°C, CAUTION >30°C (heat stress), CAUTION <10°C",
                "  - Precipitation: AVOID >1mm/hr (visibility, traction, discomfort)",
                "  - Wind: CAUTION >10m/s headwind (significantly reduces performance)",
                "  - Humidity: CAUTION >70% (increases perceived temperature 3-5°C)",
                "  - Solar radiation: CAUTION >600W/m² for long duration activities",
                "",
                "General/Unknown Activities:",
                "  - Provide activity-agnostic weather assessment",
                "  - Highlight any extreme conditions (very hot, heavy rain, strong wind)",
                "  - Recommend time windows with: moderate temp (20-28°C), no rain (<0.5mm/hr), light wind (<10m/s)",
                "",
                "HANDLING INVALID/UNCLEAR ACTIVITIES:",
                "- If activity is gibberish, unclear, or unrecognized: still provide a complete weather assessment",
                "- Focus on identifying pleasant vs harsh weather conditions",
                "- Recommend times with moderate, comfortable conditions suitable for general outdoor use",
                "- Don't reject the request - work with what you have",
                "",
                "OUTPUT FORMAT:",
                "Return a JSON object with assessment, forecast_summary, alternative_times, location_info, and summary.",
                "Structure:",
                "- assessment: {suitable, risk_level, confidence, primary_concerns, recommendation}",
                "- forecast_summary: {parameter_name: {min, max, avg, extreme_hours: [timestamps with extreme values]}}",
                "- alternative_times: [{start, end, reason}] up to 3 alternatives",
                "- location_info: {name, coordinates, interpolation_used, confidence}",
                "- summary: brief text explanation (2-3 sentences)",
                "",
                "IMPORTANT: Use forecast_summary with statistics instead of full time series to keep response concise.",
                "Only include extreme_hours (timestamps where values exceed thresholds) for key risk parameters.",
                "",
                "REASONING APPROACH:",
                "1. Identify peak risk periods (worst weather during activity time)",
                "2. Identify optimal periods (best weather in broader time range)",
                "3. Consider activity duration - longer activities need consistently good conditions",
                "4. Weight multiple factors - ONE extreme parameter can make activity unsuitable",
                "5. Be conservative with safety - err on side of caution for human safety",
                "6. Provide specific reasons tied to the activity type and weather data",
                "7. When suggesting alternatives, look at adjacent time slots (earlier/later same day, next day)",
                "",
                "INTERPOLATION CONTEXT:",
                "- If interpolation_used=true and nearest_distance_km >20km: mention lower confidence in assessment",
                "- If confidence='low' or 'very_low': explicitly note forecast uncertainty",
                "- Explain that forecast is estimated from nearby weather stations when interpolated",
                "",
                "PARAMETER UNITS (for your reference):",
                "- precipitation: mm/hour (hourly rainfall)",
                "- temperature: °C (Celsius)",
                "- wind: m/s (meters per second; 1 m/s ≈ 3.6 km/h ≈ 2.2 mph)",
                "- humidity: % (relative humidity, 0-100%)",
                "- solar_radiation: W/m² (watts per square meter - indicator of UV intensity)",
                "- cloud_cover: % (0% = clear sky, 100% = completely overcast)",
                "",
                "DATA QUALITY NOTES:",
                "- Values around -999 indicate MISSING/INVALID data - these are automatically filtered out",
                "- All forecasts use 90% confidence intervals (confidence_level = 0.9)",
                "- Larger standard_error means more forecast uncertainty",
                "- Prediction intervals that cross into negative values may indicate model uncertainty",
                "",
                "Remember: Your primary goal is USER SAFETY. Be thorough, be cautious, and always provide actionable alternatives."
            ]
        )
        
        # Conversation history (disable response validation to handle edge cases)
        # Note: tool_config is passed per-message, not at chat start
        self.chat = self.model.start_chat(response_validation=False)
        
        print(f"✓ Agent initialized")
        print(f"  Project: {project_id}")
        print(f"  Model: {model_name}")
        print(f"  Region: {region}")
    
    def ask(self, question: str, max_iterations: int = 5) -> str:
        """
        Ask the agent a question and get a response.
        
        The agent will automatically use BigQuery tools as needed and iterate
        until it has a complete answer.
        
        Args:
            question: Natural language question about the data
            max_iterations: Max tool-calling iterations to prevent infinite loops
            
        Returns:
            Agent's final response
        """
        print(f"\n{'='*70}")
        print(f"❓ Question: {question}")
        print(f"{'='*70}")
        
        # Send initial query (use generate_content to force tool calling with tool_config)
        response = self.model.generate_content(
            question,
            tools=[self.bigquery_tool],
            tool_config=self.tool_config
        )
        
        # Add to chat history manually
        self.chat._history.append(Content(role="user", parts=[Part.from_text(question)]))
        
        # Handle function calling loop
        iteration = 0
        while (response.candidates and 
               len(response.candidates) > 0 and 
               response.candidates[0].content.parts and
               len(response.candidates[0].content.parts) > 0 and
               hasattr(response.candidates[0].content.parts[0], 'function_call') and
               response.candidates[0].content.parts[0].function_call and 
               iteration < max_iterations):
            iteration += 1
            print(f"\n🤖 Agent iteration {iteration}...")
            
            # Extract function calls
            function_calls = []
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    function_calls.append(part)
            
            # Execute all function calls
            function_responses = []
            for fc in function_calls:
                func_name = fc.function_call.name
                func_args = dict(fc.function_call.args)
                
                print(f"   Calling: {func_name}")
                
                # Execute function
                result = self.bq_executor.execute_function(func_name, func_args)
                
                # Store raw forecast data if this was an activity forecast query
                # This allows us to return chart data alongside the assessment
                if func_name == "query_activity_forecast" and result.get('success'):
                    self._last_forecast_data = {
                        'forecasts': result.get('forecasts', {}),
                        'summary_stats': result.get('summary_stats', {}),
                        'location': result.get('location', {}),
                        'time_range': result.get('time_range', {}),
                        'total_records': result.get('total_records', 0)
                    }
                
                # Create function response (use "content" key per SDK examples)
                function_response = Part.from_function_response(
                    name=func_name,
                    response={"content": result}
                )
                function_responses.append(function_response)
            
            # Send function results back to model (without forcing tool use this time)
            response = self.model.generate_content(
                function_responses,
                tools=[self.bigquery_tool]
            )
            
            # Add to chat history
            self.chat._history.append(Content(role="model", parts=response.candidates[0].content.parts))
            self.chat._history.append(Content(role="user", parts=function_responses))
        
        # Extract final text response
        try:
            if response.candidates and len(response.candidates) > 0:
                parts = response.candidates[0].content.parts
                if parts and len(parts) > 0:
                    final_response = parts[0].text
                else:
                    final_response = "No response generated. The model may have encountered an issue."
            else:
                final_response = "No response candidates available."
        except Exception as e:
            final_response = f"Error extracting response: {str(e)}"
        
        print(f"\n{'='*70}")
        print(f"💡 Answer:\n{final_response}")
        print(f"{'='*70}\n")
        
        return final_response
    
    def get_chat_history(self) -> List[Content]:
        """Get full conversation history."""
        return self.chat.history
    
    def assess_activity(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        start_time: str,
        end_time: str,
        activity_type: str
    ) -> Dict[str, Any]:
        """
        High-level method to assess outdoor activity safety.
        
        This is the main entry point for activity assessment. It queries weather
        forecasts, performs spatial interpolation if needed, analyzes safety, and
        returns structured recommendations with complete forecast data for charting.
        
        Args:
            location_name: Name of location (e.g., "Mt. Apo", "Davao Beach")
            latitude: Latitude coordinate (decimal degrees)
            longitude: Longitude coordinate (decimal degrees)
            start_time: Start time in ISO format (e.g., "2024-10-04T05:00:00")
            end_time: End time in ISO format
            activity_type: Activity description (e.g., "hiking", "beach", "cycling")
            
        Returns:
            Dict with:
            - assessment: Risk assessment and suitability
            - forecast_data: Time series for all 6 parameters (for charting)
            - alternative_times: Recommended alternatives if unsuitable
            - location_info: Location and interpolation metadata
            - summary: Human-readable explanation
            - raw_response: Full agent response text
            
        Example:
            >>> agent = VertexAIAgent()
            >>> result = agent.assess_activity(
            ...     location_name="Mt. Apo",
            ...     latitude=6.987,
            ...     longitude=125.273,
            ...     start_time="2024-10-04T05:00:00",
            ...     end_time="2024-10-05T21:00:00",
            ...     activity_type="hiking"
            ... )
            >>> print(result['assessment']['suitable'])
            >>> print(result['forecast_data']['temperature'])
        """
        print(f"\n{'='*70}")
        print(f"🏃 Activity Safety Assessment")
        print(f"{'='*70}")
        print(f"  Location: {location_name} ({latitude}, {longitude})")
        print(f"  Activity: {activity_type}")
        print(f"  Time: {start_time} to {end_time}")
        print(f"{'='*70}\n")
        
        question = f"""
Assess the safety and suitability for {activity_type} at {location_name} 
(coordinates: latitude {latitude}, longitude {longitude}) 
from {start_time} to {end_time}.

Please:
1. Query the weather forecast for this location and time period
2. Analyze all weather parameters against safety thresholds for {activity_type}
3. Determine if conditions are suitable or unsuitable
4. If unsuitable, recommend specific alternative time slots
5. Return a complete JSON response with:
   - Safety assessment
   - All 6 weather parameters with full time series data
   - Alternative time recommendations
   - Location and confidence information

Return your response as a valid JSON object following the specified format.
Include ALL forecast data for charting purposes.
"""
        
        # Get agent response
        response_text = self.ask(question)
        
        # Extract JSON from response
        result = extract_json_from_response(response_text)
        
        # Add raw response for debugging/transparency
        result['raw_response'] = response_text
        
        # Attach the raw forecast data that was used for the assessment
        # This provides complete time series for charting without an extra query
        if self._last_forecast_data:
            result['chart_data'] = self._last_forecast_data
            print(f"✅ Attached chart data: {len(self._last_forecast_data.get('forecasts', {}))} parameters")
            
            # Show time points for charting
            forecasts = self._last_forecast_data.get('forecasts', {})
            if forecasts:
                first_param = list(forecasts.keys())[0]
                time_points = len(forecasts[first_param])
                print(f"   Time points: {time_points} (ready for hourly charts)")
            
            # Clear the storage
            self._last_forecast_data = None
        else:
            # No chart data captured - fetch it now as fallback
            print("⚠️  Chart data not captured during agent call, fetching now...")
            fallback_data = self.bq_executor.query_activity_forecast(
                latitude=latitude,
                longitude=longitude,
                start_time=start_time,
                end_time=end_time,
                activity_type=activity_type,
                location_name=location_name
            )
            if fallback_data.get('success'):
                result['chart_data'] = {
                    'forecasts': fallback_data.get('forecasts', {}),
                    'summary_stats': fallback_data.get('summary_stats', {}),
                    'location': fallback_data.get('location', {}),
                    'time_range': fallback_data.get('time_range', {}),
                    'total_records': fallback_data.get('total_records', 0)
                }
                print(f"✅ Fallback: Attached chart data with {len(fallback_data.get('forecasts', {}))} parameters")
            else:
                # If even fallback fails, provide empty structure
                result['chart_data'] = {
                    'forecasts': {},
                    'summary_stats': {},
                    'location': {'name': location_name, 'coordinates': {'lat': latitude, 'lon': longitude}},
                    'time_range': {'start': start_time, 'end': end_time},
                    'total_records': 0,
                    'error': 'Failed to fetch chart data'
                }
                print(f"⚠️  Warning: Could not fetch chart data")
        
        # Validate that we have the key sections
        validation_passed = True
        if 'assessment' not in result:
            print("⚠️  Warning: Response missing 'assessment' section")
            validation_passed = False
        if 'forecast_summary' not in result and 'forecast_data' not in result:
            print("⚠️  Warning: Response missing forecast summary/data section")
            validation_passed = False
        
        if validation_passed:
            print("✅ Response validation passed")
            # Show summary of what we got
            if 'forecast_summary' in result:
                param_count = len(result['forecast_summary'])
                print(f"   Forecast parameters: {param_count}/6")
            elif 'forecast_data' in result:
                param_count = len(result['forecast_data'])
                print(f"   Forecast parameters: {param_count}/6")
        
        return result
    
    def get_forecast_data(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        start_time: str,
        end_time: str
    ) -> Dict[str, Any]:
        """
        Get raw forecast data without AI analysis.
        
        This method directly queries and interpolates forecast data without going
        through the AI agent, avoiding token limits and providing complete time series.
        Use this when you need the full forecast data for charting/visualization.
        
        Args:
            location_name: Name of location
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            start_time: Start time in ISO format
            end_time: End time in ISO format
            
        Returns:
            Dict with:
            - success: bool
            - location: location metadata with interpolation info
            - forecasts: Complete time series for all 6 parameters
            - summary_stats: Min/max/avg for each parameter
        """
        print(f"\n📊 Fetching forecast data for {location_name}...")
        
        # Use the BigQuery executor directly
        result = self.bq_executor.query_activity_forecast(
            latitude=latitude,
            longitude=longitude,
            start_time=start_time,
            end_time=end_time,
            activity_type="data_query",  # Not used for this
            location_name=location_name
        )
        
        if result.get('success'):
            print(f"✅ Retrieved forecast data")
            print(f"   Parameters: {len(result.get('forecasts', {}))}/6")
            print(f"   Total records: {result.get('total_records', 0)}")
            
            # Show if any precipitation was found
            precip = result.get('forecasts', {}).get('precipitation', [])
            if precip:
                non_zero = [p for p in precip if p.get('value', 0) != 0]
                if non_zero:
                    print(f"   Precipitation: {len(non_zero)} non-zero values found")
                    max_precip = max(p.get('value', 0) for p in precip)
                    print(f"   Max precipitation: {max_precip:.2f} mm/hr")
                else:
                    print(f"   Precipitation: All values are 0 (no rain forecasted)")
        
        return result


# ============================================================================
# Main Demo
# ============================================================================

def main():
    """
    Run demo of Vertex AI agent with BigQuery tool use.
    """
    print("\n" + "="*70)
    print("🚀 Vertex AI Gemini 2.5 + BigQuery Agent POC")
    print("="*70)
    
    # Initialize agent (uses config defaults)
    agent = VertexAIAgent()
    
    # Example questions
    example_questions = [
        "What's the schema of the forecast table? What date range is covered?",
        "What is the forecasted temperature for lat=8, lon=125 on 2024-04-08?",
        "Show me precipitation forecasts for the next week with confidence intervals",
        "Which weather parameters have the highest forecast uncertainty?",
        "What are the forecasted weather patterns by hour of day for this week?",
    ]
    
    print("\n" + "="*70)
    print("📝 Example Questions:")
    for i, q in enumerate(example_questions, 1):
        print(f"  {i}. {q}")
    print("="*70)
    
    # Interactive mode
    print("\n💬 Ask questions about your weather forecasts (type 'quit' to exit)")
    print("   Or press Enter to run the first example question\n")
    
    # Run first example or accept user input
    user_input = input("Your question: ").strip()
    
    if not user_input:
        # Run first example
        response = agent.ask(example_questions[0])
    elif user_input.lower() in ['quit', 'exit', 'q']:
        print("Goodbye!")
        return
    else:
        response = agent.ask(user_input)
    
    # Continue interactive loop
    while True:
        user_input = input("\nYour question (or 'quit'): ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        if user_input:
            response = agent.ask(user_input)


if __name__ == "__main__":
    # Check if configuration is set
    if PROJECT_ID == "your-gcp-project":
        print("⚠️  Please set GCP_PROJECT_ID environment variable or update config.py")
        print("   export GCP_PROJECT_ID=your-actual-project-id")
        print("\n   Alternatively, create a .env file with:")
        print("   GCP_PROJECT_ID=your-project-id")
        print("   GCP_REGION=us-central1")
        print("   BQ_DATASET=weather")
        print("   BQ_TABLE=weather_data")
    else:
        main()

