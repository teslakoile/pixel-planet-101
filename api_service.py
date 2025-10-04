#!/usr/bin/env python3
"""
FastAPI Service for Pixel Planet Weather Agent

This API wraps the Vertex AI agent and provides REST endpoints
for weather forecasting and activity safety assessment.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Add src to path
sys.path.insert(0, 'src')

# Load .env file if it exists (for local development)
# In production (Cloud Run), environment variables are injected directly
try:
    from dotenv import load_dotenv
    env_path = Path('.env')
    if env_path.exists():
        load_dotenv(env_path)
        print("✅ Loaded .env file for local development")
except ImportError:
    pass  # python-dotenv not installed, skip

from pixel_planet.vertex_ai_agent import VertexAIAgent
from pixel_planet.config import PROJECT_ID, VERTEX_AI_MODEL, VERTEX_AI_REGION

# Initialize FastAPI app
app = FastAPI(
    title="Pixel Planet Weather Agent API",
    description="AI-powered weather forecasting and activity safety assessment API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Streamlit domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance (initialized on startup)
agent: Optional[VertexAIAgent] = None


# Request/Response Models
class ActivityAssessmentRequest(BaseModel):
    """Request model for activity assessment"""
    location_name: str = Field(..., description="Name of the location (e.g., 'Mt. Apo')")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    start_time: str = Field(..., description="Start time in ISO format (e.g., '2025-10-04T05:00:00')")
    end_time: str = Field(..., description="End time in ISO format")
    activity_type: str = Field(..., description="Activity type (e.g., 'hiking', 'beach', 'cycling')")

    class Config:
        json_schema_extra = {
            "example": {
                "location_name": "Mt. Apo",
                "latitude": 6.987,
                "longitude": 125.273,
                "start_time": "2025-10-04T05:00:00",
                "end_time": "2025-10-05T21:00:00",
                "activity_type": "hiking"
            }
        }


class ForecastDataRequest(BaseModel):
    """Request model for raw forecast data"""
    location_name: str = Field(..., description="Name of the location")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    start_time: str = Field(..., description="Start time in ISO format")
    end_time: str = Field(..., description="End time in ISO format")

    class Config:
        json_schema_extra = {
            "example": {
                "location_name": "Davao City",
                "latitude": 7.07,
                "longitude": 125.61,
                "start_time": "2025-10-04T00:00:00",
                "end_time": "2025-10-04T23:00:00"
            }
        }


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup"""
    global agent
    try:
        print("🚀 Initializing Pixel Planet Weather Agent...")
        agent = VertexAIAgent()
        print(f"✅ Agent initialized successfully")
        print(f"   Project: {PROJECT_ID}")
        print(f"   Model: {VERTEX_AI_MODEL}")
        print(f"   Region: {VERTEX_AI_REGION}")
    except Exception as e:
        print(f"❌ Failed to initialize agent: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("👋 Shutting down Pixel Planet Weather Agent API")


# Health Check Endpoints
@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Pixel Planet Weather Agent API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "assess_activity": "/api/v1/assess-activity",
            "forecast_data": "/api/v1/forecast-data"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "agent": {
            "initialized": True,
            "project": PROJECT_ID,
            "model": VERTEX_AI_MODEL
        }
    }


# API Endpoints
@app.post("/api/v1/assess-activity")
async def assess_activity(request: ActivityAssessmentRequest) -> Dict[str, Any]:
    """
    Assess outdoor activity safety based on weather forecasts.
    
    This endpoint uses AI to analyze weather conditions and provide
    safety recommendations for outdoor activities.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        print(f"\n📍 Activity Assessment Request:")
        print(f"   Location: {request.location_name} ({request.latitude}, {request.longitude})")
        print(f"   Activity: {request.activity_type}")
        print(f"   Time: {request.start_time} to {request.end_time}")
        
        result = agent.assess_activity(
            location_name=request.location_name,
            latitude=request.latitude,
            longitude=request.longitude,
            start_time=request.start_time,
            end_time=request.end_time,
            activity_type=request.activity_type
        )
        
        # Remove raw_response to reduce payload size
        if 'raw_response' in result:
            del result['raw_response']
        
        print(f"✅ Assessment completed")
        return result
        
    except Exception as e:
        print(f"❌ Error during assessment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/forecast-data")
async def get_forecast_data(request: ForecastDataRequest) -> Dict[str, Any]:
    """
    Get raw forecast data without AI analysis.
    
    Returns complete time series data for all available weather parameters.
    """
    if agent is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        print(f"\n📊 Forecast Data Request:")
        print(f"   Location: {request.location_name} ({request.latitude}, {request.longitude})")
        print(f"   Time: {request.start_time} to {request.end_time}")
        
        result = agent.get_forecast_data(
            location_name=request.location_name,
            latitude=request.latitude,
            longitude=request.longitude,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        print(f"✅ Forecast data retrieved")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching forecast data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/locations/suggest")
async def suggest_locations(
    query: str = Query(..., description="Location search query"),
    limit: int = Query(5, ge=1, le=20, description="Max number of suggestions")
) -> Dict[str, Any]:
    """
    Suggest locations based on search query.
    
    (Placeholder - could be enhanced with actual location database)
    """
    # Hardcoded popular Philippines locations for demo
    locations = [
        {"name": "Mt. Apo", "lat": 6.987, "lon": 125.273, "type": "mountain"},
        {"name": "Davao City", "lat": 7.07, "lon": 125.61, "type": "city"},
        {"name": "Manila", "lat": 14.5995, "lon": 120.9842, "type": "city"},
        {"name": "Cebu City", "lat": 10.3157, "lon": 123.8854, "type": "city"},
        {"name": "Boracay", "lat": 11.9674, "lon": 121.9248, "type": "beach"},
        {"name": "Baguio City", "lat": 16.4023, "lon": 120.5960, "type": "city"},
        {"name": "Palawan", "lat": 9.8349, "lon": 118.7384, "type": "island"},
    ]
    
    # Simple filter based on query
    query_lower = query.lower()
    filtered = [loc for loc in locations if query_lower in loc["name"].lower()]
    
    return {
        "query": query,
        "suggestions": filtered[:limit],
        "count": len(filtered)
    }


# Error Handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    # For local development
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(
        "api_service:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )

