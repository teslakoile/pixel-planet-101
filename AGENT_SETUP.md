# Vertex AI Agent with BigQuery - Setup Guide

## Overview

This POC demonstrates an AI agent using **Gemini 2.0 Flash (with reasoning)** that can:
- Query and analyze BigQuery weather forecast data using natural language
- **Assess outdoor activity safety** based on weather conditions
- **Perform spatial interpolation** when exact coordinates aren't in the dataset
- Generate and execute SQL queries automatically
- Provide structured JSON output for charting and visualization
- Recommend alternative times for activities when conditions are unsuitable
- Maintain conversation context for follow-up questions

## 🎯 Main Features

### 1. Activity Safety Assessment
Ask questions like "Is it safe to hike Mt. Apo tomorrow?" and get:
- ✅/❌ Suitability assessment
- Risk level analysis (low/medium/high/extreme)
- Specific concerns (e.g., "High UV", "Heavy rain expected")
- Alternative time slot recommendations
- Complete forecast data for all 6 weather parameters

### 2. Spatial Interpolation
Don't have exact coordinates in your dataset? No problem!
- Automatically finds 2-3 nearest forecast locations
- Uses Inverse Distance Weighting (IDW) to interpolate
- Provides confidence levels based on distance
- Works even if target is 50+ km from data points

### 3. Structured JSON Output
Perfect for building applications:
- Assessment results (suitable, risk_level, concerns, recommendation)
- Forecast data for charting (6 parameters with timestamps)
- Alternative time suggestions
- Location and confidence metadata

## Architecture

```
User Question
    ↓
Gemini 2.0 Flash (Reasoning Model)
    ↓
Function Calling → BigQuery Tool
    ↓
Execute SQL Query
    ↓
Return Results to Model
    ↓
Model Reasons & Responds
```

## Prerequisites

1. **GCP Project** with:
   - Vertex AI API enabled
   - BigQuery API enabled
   - Appropriate IAM permissions

2. **BigQuery Dataset** with weather data (or any dataset)

3. **Python 3.9+**

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements-agent.txt
```

Or install individually:
```bash
pip install google-cloud-aiplatform google-cloud-bigquery vertexai
```

### 2. Set Environment Variables

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"  # Optional, defaults to us-central1
export BQ_DATASET="weather"      # Optional, defaults to weather
export BQ_TABLE="weather_data"   # Optional, defaults to weather_data
```

### 3. Authenticate with GCP

```bash
gcloud auth application-default login
```

Or use a service account:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

## Usage

### Option 1: Activity Safety Assessment (Recommended)

```python
from pixel_planet.vertex_ai_agent import VertexAIAgent

# Initialize agent
agent = VertexAIAgent()

# Assess activity safety
result = agent.assess_activity(
    location_name="Mt. Apo",
    latitude=6.987,
    longitude=125.273,
    start_time="2024-10-04T05:00:00",
    end_time="2024-10-05T21:00:00",
    activity_type="hiking"
)

# Check results
print(f"Suitable: {result['assessment']['suitable']}")
print(f"Risk Level: {result['assessment']['risk_level']}")
print(f"Concerns: {result['assessment']['primary_concerns']}")

# Access forecast data for charting
temp_data = result['forecast_data']['temperature']
precip_data = result['forecast_data']['precipitation']
```

### Option 2: Run Demo Script

```bash
python examples/activity_assessment_demo.py
```

This runs interactive demos for:
- Hiking assessment
- Beach activities
- Cycling
- Invalid/unknown activities
- Multi-day camping

### Option 3: Run Interactive Agent

```bash
cd src
python -m pixel_planet.vertex_ai_agent
```

This starts an interactive session where you can ask questions:

```
Your question: What is the forecast for Mt. Apo this weekend?
🔍 Executing query...
💡 Answer: The forecast shows moderate temperatures...
```

### Option 2: Run Simple Demo

```bash
python examples/simple_agent_demo.py
```

This runs predefined example questions to demonstrate capabilities.

### Option 3: Use in Your Code

```python
from pixel_planet.vertex_ai_agent import VertexAIAgent

# Initialize agent
agent = VertexAIAgent(
    project_id="your-project-id",
    region="us-central1"
)

# Ask questions
response = agent.ask("What's the highest recorded temperature?")
print(response)

# Follow-up questions (context is maintained)
response = agent.ask("When did that occur?")
print(response)
```

## Example Use Cases

### Activity Safety Assessment

```python
# Example 1: Hiking
result = agent.assess_activity(
    location_name="Mt. Apo Summit Trail",
    latitude=6.987,
    longitude=125.273,
    start_time="2024-10-04T05:00:00",
    end_time="2024-10-05T21:00:00",
    activity_type="hiking"
)

# Example 2: Beach day
result = agent.assess_activity(
    location_name="Samal Island Beach",
    latitude=7.073,
    longitude=125.728,
    start_time="2024-10-06T08:00:00",
    end_time="2024-10-06T16:00:00",
    activity_type="beach swimming"
)

# Example 3: Cycling
result = agent.assess_activity(
    location_name="Davao City",
    latitude=7.0,
    longitude=125.5,
    start_time="2024-10-07T06:00:00",
    end_time="2024-10-07T09:00:00",
    activity_type="cycling"
)
```

### Natural Language Queries

The agent can also answer general questions:

**Forecast Queries:**
- "What's the weather forecast for Davao City this weekend?"
- "Will it rain at Mt. Apo tomorrow morning?"
- "What are the UV levels for beach activities today?"

**Activity-Specific:**
- "Is it safe to hike Mt. Apo on Saturday?"
- "When is the best time for outdoor photography this week?"
- "Recommend good beach days for the next 3 days"

**Temporal Patterns:**
- "What are typical weather patterns by hour of day?"
- "Which days this week have the best weather?"
- "Compare morning vs evening conditions"

**Spatial Analysis:**
- "Which location has the best weather for hiking this weekend?"
- "Compare rainfall across different areas"

## JSON Output Structure

The `assess_activity()` method returns a structured JSON object:

```json
{
  "assessment": {
    "suitable": true,
    "risk_level": "low",
    "confidence": "high",
    "primary_concerns": ["Moderate UV levels", "Afternoon heat"],
    "recommendation": "Good conditions for hiking. Start early to avoid afternoon heat."
  },
  "alternative_times": [
    {
      "start": "2024-10-05T05:00:00",
      "end": "2024-10-05T10:00:00",
      "reason": "Cooler temperatures and lower UV in early morning"
    }
  ],
  "forecast_data": {
    "precipitation": [
      {"timestamp": "2024-10-04T05:00:00", "value": 0.1, "lower": 0.0, "upper": 0.3},
      {"timestamp": "2024-10-04T06:00:00", "value": 0.2, "lower": 0.0, "upper": 0.5},
      ...
    ],
    "temperature": [...],
    "wind": [...],
    "humidity": [...],
    "solar_radiation": [...],
    "cloud_cover": [...]
  },
  "location_info": {
    "name": "Mt. Apo",
    "coordinates": {"lat": 6.987, "lon": 125.273},
    "interpolation_used": true,
    "nearest_distance_km": 12.5,
    "confidence": "medium",
    "confidence_message": "Forecast interpolated from locations 12.5km away. Moderate confidence."
  },
  "summary": "Human-readable summary of the assessment and recommendations",
  "raw_response": "Full text response from the agent..."
}
```

### Using Forecast Data for Charts

The `forecast_data` section contains time series arrays perfect for visualization:

```python
import matplotlib.pyplot as plt
import pandas as pd

result = agent.assess_activity(...)

# Extract temperature data
temp_data = result['forecast_data']['temperature']
df = pd.DataFrame(temp_data)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Plot with confidence intervals
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['value'], label='Forecast', linewidth=2)
plt.fill_between(df['timestamp'], df['lower'], df['upper'], alpha=0.3, label='90% Confidence')
plt.xlabel('Time')
plt.ylabel('Temperature (°C)')
plt.title('Temperature Forecast')
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

## Spatial Interpolation

### How It Works

When you request a forecast for coordinates not in your dataset:

1. **Find Nearest Points**: Query finds all forecast locations within 100km
2. **Inverse Distance Weighting (IDW)**: Interpolates using formula:
   ```
   value = Σ(w_i * v_i) / Σ(w_i)
   where w_i = 1 / (distance_i ^ 2)
   ```
3. **Confidence Assessment**:
   - `high`: Nearest point < 1km away
   - `medium`: Nearest point 1-20km away
   - `low`: Nearest point 20-50km away
   - `very_low`: Nearest point > 50km away

### Example

```python
# Your dataset has 5 locations in Davao Region
# User requests forecast for Mt. Apo (6.987, 125.273)

result = agent.assess_activity(
    location_name="Mt. Apo",
    latitude=6.987,  # Not exactly in dataset
    longitude=125.273,
    start_time="2024-10-04T05:00:00",
    end_time="2024-10-04T18:00:00",
    activity_type="hiking"
)

# Check interpolation metadata
loc_info = result['location_info']
print(f"Interpolation used: {loc_info['interpolation_used']}")
print(f"Nearest data point: {loc_info['nearest_distance_km']}km away")
print(f"Confidence: {loc_info['confidence']}")
print(f"Message: {loc_info['confidence_message']}")
```

## Safety Thresholds

The agent uses activity-specific safety thresholds:

### Hiking/Trekking
- 🌡️ Temperature: CAUTION >32°C, UNSAFE >35°C
- 🌧️ Precipitation: CAUTION >2mm/hr, UNSAFE >10mm/hr
- 💨 Wind: CAUTION >15m/s, UNSAFE >20m/s
- ☀️ Solar/UV: CAUTION >800W/m², UNSAFE >1000W/m²

### Beach Activities
- 🌡️ Temperature: OPTIMAL 25-32°C
- 🌧️ Precipitation: AVOID >1mm/hr, UNSAFE >5mm/hr
- 💨 Wind: CAUTION >10m/s, UNSAFE >15m/s
- ☀️ Solar/UV: CAUTION >700W/m²

### Cycling/Running
- 🌡️ Temperature: OPTIMAL 15-25°C, CAUTION >30°C
- 🌧️ Precipitation: AVOID >1mm/hr
- 💨 Wind: CAUTION >10m/s (headwind)
- 💧 Humidity: CAUTION >70%

*Thresholds can be customized in `vertex_ai_agent.py` system instructions*

## Customization

### Use Different Models

```python
agent = VertexAIAgent(
    project_id="your-project-id",
    model_name="gemini-2.0-flash-exp"  # Current reasoning model
)
```

Available models:
- `gemini-2.0-flash-exp` - Fast with reasoning (recommended)
- `gemini-1.5-pro` - More powerful, slower
- `gemini-1.5-flash` - Fast, good for simple queries

### Customize System Instructions

Edit the `system_instruction` in `vertex_ai_agent.py` to:
- Change the agent's personality
- Add domain-specific knowledge
- Modify query guidelines
- Add safety constraints

### Add More Tools

Extend the agent with additional capabilities:

```python
# Add data visualization
viz_func = FunctionDeclaration(
    name="create_chart",
    description="Create a chart from query results",
    parameters={...}
)

# Add weather forecasting
forecast_func = FunctionDeclaration(
    name="get_forecast",
    description="Get ML forecast from BQML models",
    parameters={...}
)
```

### Connect to Different Datasets

Update the configuration:

```python
BQ_TABLE_FULL = "your-project.your-dataset.your-table"
```

And modify the system instructions to describe your data schema.

## Troubleshooting

### Error: "Permission denied on project"
- Ensure Vertex AI API is enabled: `gcloud services enable aiplatform.googleapis.com`
- Check IAM permissions: need `aiplatform.user` role

### Error: "Model not found"
- Gemini 2.0 Flash is in preview, ensure you have access
- Try `gemini-1.5-pro` as alternative

### Error: "Invalid SQL syntax"
- The model uses BigQuery SQL dialect
- Check that table name is fully qualified: `project.dataset.table`

### Agent gives wrong answers
- The model may hallucinate without data
- Ensure it's actually calling the `query_bigquery` function (check logs)
- Try more specific questions

### Slow responses
- First call initializes the model (slower)
- Subsequent calls use the same session (faster)
- Complex queries take longer to execute

## Cost Considerations

**Vertex AI Pricing:**
- Gemini 2.0 Flash: ~$0.075 per 1M input tokens, ~$0.30 per 1M output tokens
- Each query + response: typically 1-5K tokens (~$0.001)

**BigQuery Pricing:**
- On-demand: $6.25 per TB scanned
- Weather data queries: typically scan <100MB per query (~$0.0006)

**Example costs:**
- 100 agent questions: ~$0.10 (Vertex AI) + ~$0.06 (BigQuery) = **~$0.16**
- Very affordable for POC and testing!

## Next Steps

1. **Connect to your dataset** - Update config with your table
2. **Test example questions** - Try the demo scripts
3. **Customize agent** - Adjust system instructions for your use case
4. **Add to application** - Integrate into web app or API
5. **Monitor usage** - Track costs and performance

## Advanced: Multi-Agent System

For production, consider:
- **Routing agent** - Directs questions to specialized agents
- **SQL validation agent** - Reviews queries before execution
- **Visualization agent** - Creates charts from results
- **Forecast agent** - Calls BQML models for predictions

## Resources

- [Vertex AI Gemini API Docs](https://cloud.google.com/vertex-ai/generative-ai/docs)
- [Function Calling Guide](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling)
- [BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql)

---

**Need Help?** Open an issue or check the example scripts for working code.

