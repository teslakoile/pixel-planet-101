#!/usr/bin/env python3
"""
Demo: Vertex AI Agent with Weather Forecasts and Charts

This script demonstrates:
1. Activity safety assessment using AI agent
2. Extracting chart data from the response
3. Creating visualizations for all 6 weather parameters
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env
env_file = Path('.env')
if env_file.exists():
    print("📄 Loading environment from .env...")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('export '):
                line = line[7:]
            if '=' in line:
                key, value = line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value
    print("✅ Environment loaded\n")

# Add src to path
sys.path.insert(0, 'src')

from pixel_planet.vertex_ai_agent import VertexAIAgent
import json


def print_assessment(result):
    """Print the AI assessment in a readable format"""
    print("\n" + "="*70)
    print("🤖 AI ASSESSMENT")
    print("="*70)
    
    if 'assessment' in result:
        assessment = result['assessment']
        print(f"✓ Suitable: {assessment.get('suitable')}")
        print(f"✓ Risk Level: {assessment.get('risk_level')}")
        print(f"✓ Confidence: {assessment.get('confidence')}")
        
        concerns = assessment.get('primary_concerns')
        if isinstance(concerns, list):
            print(f"✓ Primary Concerns:")
            for concern in concerns:
                print(f"  • {concern}")
        else:
            print(f"✓ Primary Concerns: {concerns}")
        
        print(f"\n📝 Recommendation:")
        print(f"   {assessment.get('recommendation')}")
    
    if 'summary' in result:
        print(f"\n📊 Summary:")
        print(f"   {result['summary']}")


def print_forecast_summary(result):
    """Print forecast summary statistics"""
    print("\n" + "="*70)
    print("🌤️  FORECAST SUMMARY")
    print("="*70)
    
    if 'forecast_summary' in result:
        for param, stats in result['forecast_summary'].items():
            print(f"\n{param.upper().replace('_', ' ')}:")
            print(f"  Min: {stats.get('min')}")
            print(f"  Max: {stats.get('max')}")
            print(f"  Avg: {stats.get('avg')}")
            
            extreme_hours = stats.get('extreme_hours', [])
            if extreme_hours:
                print(f"  ⚠️  Extreme hours: {len(extreme_hours)} time points")
                print(f"     First: {extreme_hours[0]}")
                print(f"     Last: {extreme_hours[-1]}")


def print_alternatives(result):
    """Print alternative time recommendations"""
    if 'alternative_times' in result and result['alternative_times']:
        print("\n" + "="*70)
        print("⏰ ALTERNATIVE TIMES")
        print("="*70)
        
        for i, alt in enumerate(result['alternative_times'], 1):
            print(f"\n{i}. {alt.get('start')} to {alt.get('end')}")
            print(f"   Reason: {alt.get('reason')}")


def print_chart_data_info(result):
    """Print information about available chart data"""
    print("\n" + "="*70)
    print("📈 CHART DATA")
    print("="*70)
    
    if 'chart_data' not in result:
        print("❌ No chart data available")
        return
    
    chart_data = result['chart_data']
    
    print(f"\n✅ Chart data available for visualization")
    print(f"   Location: {chart_data.get('location', {}).get('name')}")
    print(f"   Total records: {chart_data.get('total_records', 0)}")
    
    forecasts = chart_data.get('forecasts', {})
    print(f"\n   Parameters ({len(forecasts)}/6):")
    
    for param, data in forecasts.items():
        if data:
            print(f"   • {param}: {len(data)} time points")
            print(f"     Range: {data[0]['timestamp']} to {data[-1]['timestamp']}")
            values = [d['value'] for d in data if d['value'] is not None]
            if values:
                print(f"     Values: {min(values):.2f} to {max(values):.2f}")
    
    # Location info
    location = chart_data.get('location', {})
    if location:
        print(f"\n   📍 Location Info:")
        print(f"      Interpolation used: {location.get('interpolation_used')}")
        print(f"      Nearest distance: {location.get('nearest_distance_km')}km")
        print(f"      Confidence: {location.get('confidence')}")


def create_charts(result, output_dir='charts'):
    """
    Create charts for all weather parameters.
    
    Requires: matplotlib, pandas
    """
    try:
        import matplotlib.pyplot as plt
        import pandas as pd
        from datetime import datetime
    except ImportError:
        print("\n⚠️  Matplotlib/Pandas not installed. Skipping chart generation.")
        print("   Install with: pip install matplotlib pandas")
        return
    
    if 'chart_data' not in result:
        print("\n❌ No chart data available for visualization")
        return
    
    chart_data = result['chart_data']
    forecasts = chart_data.get('forecasts', {})
    
    if not forecasts:
        print("\n❌ No forecast data to chart")
        return
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    print(f"\n📊 Creating charts in '{output_dir}/'...")
    
    # Create a figure with subplots for all parameters
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    fig.suptitle(
        f"Weather Forecast for {chart_data.get('location', {}).get('name', 'Location')}\n"
        f"{chart_data.get('time_range', {}).get('start')} to {chart_data.get('time_range', {}).get('end')}",
        fontsize=16,
        fontweight='bold'
    )
    
    parameters = ['precipitation', 'temperature', 'wind', 'humidity', 'solar_radiation', 'cloud_cover']
    units = {
        'precipitation': 'mm/hr',
        'temperature': '°C',
        'wind': 'm/s',
        'humidity': '%',
        'solar_radiation': 'W/m²',
        'cloud_cover': '%'
    }
    
    for idx, param in enumerate(parameters):
        row = idx // 2
        col = idx % 2
        ax = axes[row, col]
        
        data = forecasts.get(param, [])
        if not data:
            ax.text(0.5, 0.5, f'No data for {param}', 
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(param.replace('_', ' ').title())
            continue
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Plot main line
        ax.plot(df['timestamp'], df['value'], 
               label=param.replace('_', ' ').title(), 
               linewidth=2, color='#2E86AB', marker='o', markersize=3)
        
        # Add confidence intervals if available
        if 'lower' in df.columns and 'upper' in df.columns:
            ax.fill_between(df['timestamp'], df['lower'], df['upper'], 
                           alpha=0.2, color='#2E86AB', label='90% Confidence Interval')
        
        # Styling
        ax.set_xlabel('Time', fontsize=10)
        ax.set_ylabel(f'{param.replace("_", " ").title()} ({units.get(param, "")})', fontsize=10)
        ax.set_title(param.replace('_', ' ').title(), fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(fontsize=8)
        ax.tick_params(axis='x', rotation=45)
        
        # Format x-axis
        import matplotlib.dates as mdates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_path / 'weather_forecast.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Saved: {output_file}")
    
    # Also create individual charts for each parameter
    for param in parameters:
        data = forecasts.get(param, [])
        if not data:
            continue
        
        fig, ax = plt.subplots(figsize=(10, 6))
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Plot main line
        ax.plot(df['timestamp'], df['value'], 
               linewidth=2.5, color='#2E86AB', marker='o', markersize=4)
        
        # Add confidence intervals
        if 'lower' in df.columns and 'upper' in df.columns:
            ax.fill_between(df['timestamp'], df['lower'], df['upper'], 
                           alpha=0.2, color='#2E86AB')
        
        # Styling
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel(f'{param.replace("_", " ").title()} ({units.get(param, "")})', fontsize=12)
        ax.set_title(
            f'{param.replace("_", " ").title()} Forecast\n'
            f'{chart_data.get("location", {}).get("name", "Location")}',
            fontsize=14, fontweight='bold'
        )
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.tick_params(axis='x', rotation=45)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        
        plt.tight_layout()
        
        # Save individual chart
        output_file = output_path / f'{param}.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"✅ Saved: {output_file}")
    
    plt.close('all')
    print(f"\n✅ All charts saved to '{output_dir}/'")


def save_results(result, output_file='assessment_result.json'):
    """Save full results to JSON file"""
    print(f"\n💾 Saving results to {output_file}...")
    
    # Remove raw_response to keep JSON clean
    result_clean = result.copy()
    if 'raw_response' in result_clean:
        del result_clean['raw_response']
    
    with open(output_file, 'w') as f:
        json.dump(result_clean, f, indent=2)
    
    print(f"✅ Results saved")


def main():
    """Main demo function"""
    print("\n" + "="*70)
    print("🚀 Vertex AI Weather Agent Demo")
    print("="*70)
    
    # Initialize agent
    print("\n1️⃣ Initializing agent...")
    agent = VertexAIAgent()
    
    # Sanity test: verify raw data fetch works (no LLM, just data)
    print("\n🔧 Running sanity test (raw data fetch)...")
    raw_test = agent.get_forecast_data(
        location_name="Mt. Apo",
        latitude=6.987,
        longitude=125.273,
        start_time="2025-10-04T05:00:00",
        end_time="2025-10-05T21:00:00",
    )
    
    if raw_test["success"] and raw_test.get("forecasts"):
        print(f"✅ Sanity test PASSED: {raw_test.get('total_records')} records retrieved")
        print(f"   Parameters: {list(raw_test.get('forecasts', {}).keys())}")
    else:
        print(f"❌ Sanity test FAILED: {raw_test.get('error', 'Unknown error')}")
        print("   Cannot proceed with agent demo. Check your BigQuery data.")
        return
    
    # Example activity assessment
    print("\n2️⃣ Assessing activity safety...")
    result = agent.assess_activity(
        location_name="Mt. Apo",
        latitude=6.987,
        longitude=125.273,
        start_time="2025-10-04T05:00:00",
        end_time="2025-10-05T21:00:00",
        activity_type="hiking"
    )
    
    # Display results
    print_assessment(result)
    print_forecast_summary(result)
    print_alternatives(result)
    print_chart_data_info(result)
    
    # Save results
    save_results(result, 'mt_apo_hiking_assessment.json')
    
    # Create charts
    create_charts(result, output_dir='mt_apo_charts')
    
    print("\n" + "="*70)
    print("✅ Demo complete!")
    print("="*70)


if __name__ == "__main__":
    main()

