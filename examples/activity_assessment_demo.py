"""
Activity Safety Assessment Demo

Demonstrates how to use the Vertex AI agent to assess outdoor activity safety
with weather forecasts, spatial interpolation, and structured JSON output.
"""

import os
import sys
import json
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pixel_planet.vertex_ai_agent import VertexAIAgent
from pixel_planet.config import PROJECT_ID


def print_separator(title=""):
    """Print a nice separator."""
    print("\n" + "="*70)
    if title:
        print(f"  {title}")
        print("="*70)
    else:
        print("="*70)


def print_assessment(result: dict):
    """Pretty print assessment results."""
    if 'assessment' in result:
        assessment = result['assessment']
        print("\n📊 ASSESSMENT:")
        print(f"  Suitable: {'✅ YES' if assessment.get('suitable') else '❌ NO'}")
        print(f"  Risk Level: {assessment.get('risk_level', 'unknown').upper()}")
        print(f"  Confidence: {assessment.get('confidence', 'unknown')}")
        print(f"  Concerns: {', '.join(assessment.get('primary_concerns', []))}")
        print(f"  Recommendation: {assessment.get('recommendation', 'N/A')}")
    
    if 'location_info' in result:
        loc = result['location_info']
        print("\n📍 LOCATION:")
        print(f"  Name: {loc.get('name')}")
        print(f"  Coordinates: {loc.get('coordinates')}")
        print(f"  Interpolation: {'Yes' if loc.get('interpolation_used') else 'No'}")
        print(f"  Confidence: {loc.get('confidence')}")
    
    if 'alternative_times' in result and result['alternative_times']:
        print("\n⏰ ALTERNATIVE TIMES:")
        for i, alt in enumerate(result['alternative_times'][:3], 1):
            print(f"  {i}. {alt.get('start')} to {alt.get('end')}")
            print(f"     Reason: {alt.get('reason')}")
    
    if 'forecast_data' in result:
        print("\n🌤️  FORECAST DATA:")
        for param, data in result['forecast_data'].items():
            if data:
                print(f"  {param}: {len(data)} time points")
    
    if 'summary' in result:
        print(f"\n💬 SUMMARY:\n{result['summary']}\n")


def demo_hiking_assessment(agent):
    """Demo: Hiking on Mt. Apo"""
    print_separator("DEMO 1: Hiking Assessment - Mt. Apo")
    
    result = agent.assess_activity(
        location_name="Mt. Apo",
        latitude=6.987,
        longitude=125.273,
        start_time="2024-10-04T05:00:00",
        end_time="2024-10-05T21:00:00",
        activity_type="hiking"
    )
    
    print_assessment(result)
    return result


def demo_beach_activity(agent):
    """Demo: Beach day at Samal Island"""
    print_separator("DEMO 2: Beach Activity - Samal Island")
    
    # Samal Island approximate coordinates
    result = agent.assess_activity(
        location_name="Samal Island Beach",
        latitude=7.073,
        longitude=125.728,
        start_time="2024-10-06T08:00:00",
        end_time="2024-10-06T16:00:00",
        activity_type="beach swimming and sunbathing"
    )
    
    print_assessment(result)
    return result


def demo_cycling(agent):
    """Demo: Cycling around Davao City"""
    print_separator("DEMO 3: Cycling - Davao City")
    
    result = agent.assess_activity(
        location_name="Davao City",
        latitude=7.0,
        longitude=125.5,
        start_time="2024-10-07T06:00:00",
        end_time="2024-10-07T09:00:00",
        activity_type="road cycling"
    )
    
    print_assessment(result)
    return result


def demo_invalid_activity(agent):
    """Demo: Invalid/gibberish activity (should still work)"""
    print_separator("DEMO 4: Invalid Activity - General Assessment")
    
    result = agent.assess_activity(
        location_name="Random Location",
        latitude=7.2,
        longitude=125.3,
        start_time="2024-10-08T10:00:00",
        end_time="2024-10-08T14:00:00",
        activity_type="xyzabc123nonsense"
    )
    
    print_assessment(result)
    return result


def demo_multiday_camping(agent):
    """Demo: Multi-day camping trip"""
    print_separator("DEMO 5: Multi-Day Camping")
    
    result = agent.assess_activity(
        location_name="Camping Site near Eden Nature Park",
        latitude=7.15,
        longitude=125.45,
        start_time="2024-10-10T14:00:00",
        end_time="2024-10-12T10:00:00",
        activity_type="camping"
    )
    
    print_assessment(result)
    return result


def save_results_to_file(results: dict, filename: str = "assessment_results.json"):
    """Save assessment results to JSON file."""
    # Remove raw_response to keep file clean
    clean_results = {k: v for k, v in results.items() if k != 'raw_response'}
    
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'w') as f:
        json.dump(clean_results, f, indent=2)
    
    print(f"\n💾 Results saved to: {filepath}")


def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("🚀 Activity Safety Assessment Demo")
    print("   Vertex AI + BigQuery + Spatial Interpolation")
    print("="*70)
    
    # Check configuration
    if PROJECT_ID == "your-gcp-project":
        print("❌ Please set GCP_PROJECT_ID environment variable or update config.py")
        print("   Example: export GCP_PROJECT_ID=my-project-123")
        return
    
    print(f"\n✓ Using project: {PROJECT_ID}")
    
    # Initialize agent
    print("\n🤖 Initializing agent...")
    agent = VertexAIAgent()
    
    # Run demos
    demos = [
        ("Hiking", demo_hiking_assessment),
        ("Beach", demo_beach_activity),
        ("Cycling", demo_cycling),
        ("Invalid Activity", demo_invalid_activity),
        ("Multi-day Camping", demo_multiday_camping)
    ]
    
    print("\n📋 Available demos:")
    for i, (name, _) in enumerate(demos, 1):
        print(f"  {i}. {name}")
    print(f"  {len(demos) + 1}. Run all demos")
    
    choice = input("\nSelect demo (1-6, or Enter for all): ").strip()
    
    if not choice or choice == str(len(demos) + 1):
        # Run all demos
        results = {}
        for name, demo_func in demos:
            result = demo_func(agent)
            results[name] = result
            input("\nPress Enter to continue to next demo...")
        
        # Save all results
        save_results_to_file(results, "all_demo_results.json")
    else:
        # Run selected demo
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(demos):
                name, demo_func = demos[idx]
                result = demo_func(agent)
                save_results_to_file(result, f"{name.lower().replace(' ', '_')}_result.json")
            else:
                print("Invalid selection")
        except ValueError:
            print("Invalid input")
    
    print("\n✅ Demo complete!")
    print("\nNext steps:")
    print("  1. Review the JSON output structure")
    print("  2. Use forecast_data arrays to create charts")
    print("  3. Integrate into your application")
    print("  4. Customize safety thresholds in vertex_ai_agent.py\n")


if __name__ == "__main__":
    main()

