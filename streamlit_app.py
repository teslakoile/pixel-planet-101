"""
Pixel Planet Weather Agent - Streamlit App

A simple web interface to interact with the deployed Weather Agent API.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# API Configuration
API_BASE_URL = "https://pixel-planet-api-eixw6uscdq-uc.a.run.app"

# Page config
st.set_page_config(
    page_title="Pixel Planet Weather Agent",
    page_icon="🌍",
    layout="wide"
)

# Title and description
st.title("🌍 Pixel Planet Weather Agent")
st.markdown("""
Get AI-powered weather forecasts and activity safety assessments for any location in the Philippines.
""")

# Sidebar for inputs
st.sidebar.header("📍 Activity Details")

# Location inputs
location_name = st.sidebar.text_input(
    "Location Name",
    value="Mt. Apo",
    help="Name of the location (e.g., Mt. Apo, Boracay, Manila)"
)

col1, col2 = st.sidebar.columns(2)
with col1:
    latitude = st.number_input(
        "Latitude",
        value=6.987,
        min_value=-90.0,
        max_value=90.0,
        step=0.001,
        format="%.3f",
        help="Latitude in decimal degrees"
    )
with col2:
    longitude = st.number_input(
        "Longitude",
        value=125.273,
        min_value=-180.0,
        max_value=180.0,
        step=0.001,
        format="%.3f",
        help="Longitude in decimal degrees"
    )

st.sidebar.markdown("---")

# Time inputs
st.sidebar.subheader("⏰ Time Range")

# Default to tomorrow 5 AM to next day 9 PM
default_start = datetime.now().replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(days=1)
default_end = default_start + timedelta(hours=40)

start_date = st.sidebar.date_input(
    "Start Date",
    value=default_start.date()
)
start_time = st.sidebar.time_input(
    "Start Time",
    value=default_start.time()
)

end_date = st.sidebar.date_input(
    "End Date",
    value=default_end.date()
)
end_time = st.sidebar.time_input(
    "End Time",
    value=default_end.time()
)

# Combine date and time
start_datetime = datetime.combine(start_date, start_time)
end_datetime = datetime.combine(end_date, end_time)

st.sidebar.markdown("---")

# Activity type
st.sidebar.subheader("🎯 Activity Type")
activity_type = st.sidebar.selectbox(
    "What activity are you planning?",
    [
        "hiking",
        "beach day",
        "cycling",
        "outdoor concert",
        "camping",
        "surfing",
        "photography",
        "picnic",
        "running",
        "fishing"
    ],
    index=0
)

st.sidebar.markdown("---")

# Assess button
assess_button = st.sidebar.button("🚀 Assess Activity", type="primary", use_container_width=True)

# Main content area
if assess_button:
    # Validate inputs
    if end_datetime <= start_datetime:
        st.error("❌ End time must be after start time!")
        st.stop()
    
    # Prepare API request
    payload = {
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "start_time": start_datetime.isoformat(),
        "end_time": end_datetime.isoformat(),
        "activity_type": activity_type
    }
    
    # Show loading spinner
    with st.spinner("🤖 AI Agent is analyzing weather data..."):
        try:
            # Call API
            response = requests.post(
                f"{API_BASE_URL}/api/v1/assess-activity",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            
            # Debug: Show raw response in an expander
            with st.expander("🔍 Debug: Raw API Response", expanded=False):
                st.json(result)
            
            # Display results
            st.success("✅ Assessment complete!")
            
            # =====================================================================
            # SECTION 1: AI Assessment
            # =====================================================================
            st.header("🤖 AI Assessment")
            
            # Show summary if available
            if result.get('summary'):
                st.markdown(f"**Summary:** {result['summary']}")
                st.markdown("---")
            
            assessment = result.get('assessment', {})
            
            # Suitability banner
            suitable = assessment.get('suitable', False)
            risk_level = assessment.get('risk_level', 'unknown')
            
            if suitable:
                st.success(f"✅ **SUITABLE** for {activity_type}")
            else:
                st.error(f"⚠️ **NOT RECOMMENDED** for {activity_type}")
            
            # Risk level with color
            risk_colors = {
                'low': '🟢',
                'medium': '🟡',
                'high': '🔴',
                'very_high': '🔴'
            }
            risk_icon = risk_colors.get(risk_level.lower(), '⚪')
            
            # Show risk and confidence in columns
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Risk Level:** {risk_icon} {risk_level.upper()}")
            with col2:
                confidence = assessment.get('confidence', 'unknown')
                st.markdown(f"**Confidence:** {confidence.upper()}")
            
            # Primary Concerns
            if assessment.get('primary_concerns'):
                st.subheader("⚠️ Primary Concerns")
                for concern in assessment['primary_concerns']:
                    st.warning(f"• {concern}")
            
            # Recommendation (single text)
            if assessment.get('recommendation'):
                st.subheader("💡 Recommendation")
                st.info(assessment['recommendation'])
            
            # Alternative times
            alternative_times = result.get('alternative_times', [])
            if alternative_times:
                st.subheader("🔄 Better Times")
                for alt in alternative_times:
                    if isinstance(alt, dict):
                        st.success(f"**{alt.get('start', '')} to {alt.get('end', '')}**\n\n{alt.get('reason', '')}")
                    else:
                        st.success(f"• {alt}")
            
            st.markdown("---")
            
            # =====================================================================
            # SECTION 2: Forecast Summary
            # =====================================================================
            st.header("📊 Forecast Summary")
            
            forecast_summary = result.get('forecast_summary', {})
            
            if forecast_summary:
                # Create 3 columns for summary cards
                col1, col2, col3 = st.columns(3)
                
                params = list(forecast_summary.keys())
                for idx, param in enumerate(params):
                    stats = forecast_summary[param]
                    
                    # Skip if stats is None or missing required keys
                    if not stats or not isinstance(stats, dict):
                        continue
                    if 'avg' not in stats or 'min' not in stats or 'max' not in stats:
                        continue
                    
                    col = [col1, col2, col3][idx % 3]
                    
                    with col:
                        st.metric(
                            label=param.replace('_', ' ').title(),
                            value=f"{stats['avg']:.1f}",
                            delta=f"Range: {stats['min']:.1f} - {stats['max']:.1f}"
                        )
            
            st.markdown("---")
            
            # =====================================================================
            # SECTION 3: Location Info
            # =====================================================================
            st.header("📍 Location Information")
            
            # Try both 'location_info' and 'location' keys for compatibility
            location = result.get('location_info', result.get('location', {}))
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Location", location.get('name', 'Unknown'))
            
            with col2:
                coords = location.get('coordinates', {})
                st.metric("Coordinates", f"{coords.get('lat', 0):.3f}, {coords.get('lon', 0):.3f}")
            
            with col3:
                interpolation = "Yes" if location.get('interpolation_used', False) else "No"
                st.metric("Interpolation", interpolation)
            
            with col4:
                confidence = location.get('confidence', 'unknown').upper()
                st.metric("Confidence", confidence)
            
            # Display confidence message if available
            if location.get('confidence_message'):
                st.info(f"ℹ️ {location['confidence_message']}")
            
            st.markdown("---")
            
            # =====================================================================
            # SECTION 4: Weather Charts
            # =====================================================================
            st.header("📈 Weather Forecast Charts")
            
            chart_data = result.get('chart_data', {})
            # Extract forecasts from chart_data
            forecasts = chart_data.get('forecasts', {}) if isinstance(chart_data, dict) else {}
            
            if forecasts:
                # Parameter info and units
                param_info = {
                    'precipitation': {'name': 'Precipitation', 'unit': 'mm', 'color': '#1f77b4'},
                    'temperature': {'name': 'Temperature', 'unit': '°C', 'color': '#ff7f0e'},
                    'wind': {'name': 'Wind Speed', 'unit': 'm/s', 'color': '#2ca02c'},
                    'humidity': {'name': 'Humidity', 'unit': '%', 'color': '#d62728'},
                    'solar_radiation': {'name': 'Solar Radiation', 'unit': 'W/m²', 'color': '#9467bd'},
                    'cloud_cover': {'name': 'Cloud Cover', 'unit': '%', 'color': '#8c564b'}
                }
                
                # Create chart for each parameter
                for param, data_points in forecasts.items():
                    if not data_points or not isinstance(data_points, list):
                        continue
                    
                    info = param_info.get(param, {'name': param.title(), 'unit': '', 'color': '#7f7f7f'})
                    
                    # Convert to DataFrame
                    try:
                        df = pd.DataFrame(data_points)
                        if df.empty or 'timestamp' not in df.columns or 'value' not in df.columns:
                            continue
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                    except Exception as e:
                        st.warning(f"Could not parse data for {param}: {str(e)}")
                        continue
                    
                    # Create plotly figure
                    fig = go.Figure()
                    
                    # Add confidence interval (if available)
                    if 'lower' in df.columns and 'upper' in df.columns:
                        fig.add_trace(go.Scatter(
                            x=df['timestamp'].tolist() + df['timestamp'].tolist()[::-1],
                            y=df['upper'].tolist() + df['lower'].tolist()[::-1],
                            fill='toself',
                            fillcolor=f"rgba{tuple(list(int(info['color'][i:i+2], 16) for i in (1, 3, 5)) + [0.2])}",
                            line=dict(color='rgba(255,255,255,0)'),
                            hoverinfo="skip",
                            showlegend=True,
                            name='Confidence Interval'
                        ))
                    
                    # Add main forecast line
                    fig.add_trace(go.Scatter(
                        x=df['timestamp'],
                        y=df['value'],
                        mode='lines+markers',
                        name='Forecast',
                        line=dict(color=info['color'], width=2),
                        marker=dict(size=4)
                    ))
                    
                    # Update layout
                    fig.update_layout(
                        title=f"{info['name']} Forecast",
                        xaxis_title="Time",
                        yaxis_title=f"{info['name']} ({info['unit']})",
                        hovermode='x unified',
                        height=400,
                        showlegend=True
                    )
                    
                    # Display chart
                    st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.warning("No chart data available")
            
        except requests.exceptions.Timeout:
            st.error("❌ Request timed out. The API might be processing a large dataset. Please try again.")
        except requests.exceptions.RequestException as e:
            st.error(f"❌ API Error: {str(e)}")
            if hasattr(e.response, 'text'):
                st.code(e.response.text)
        except Exception as e:
            st.error(f"❌ Unexpected Error: {str(e)}")
            st.exception(e)

else:
    # Show placeholder when no assessment has been run
    st.info("👈 Enter your activity details in the sidebar and click **Assess Activity** to get started!")
    
    # Show some example locations
    st.subheader("📍 Popular Locations")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **🏔️ Mt. Apo**
        - Lat: 6.987
        - Lon: 125.273
        - Best for: Hiking, Camping
        """)
    
    with col2:
        st.markdown("""
        **🏖️ Boracay**
        - Lat: 11.967
        - Lon: 121.925
        - Best for: Beach, Swimming
        """)
    
    with col3:
        st.markdown("""
        **🌆 Manila**
        - Lat: 14.599
        - Lon: 120.984
        - Best for: Outdoor Events
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <small>Powered by Vertex AI Gemini 2.5 & BigQuery | Pixel Planet 🌍</small>
</div>
""", unsafe_allow_html=True)

