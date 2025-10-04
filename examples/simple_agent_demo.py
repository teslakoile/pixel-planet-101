"""
Simple demo script for Vertex AI Agent with BigQuery

This is a minimal example showing the core functionality.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pixel_planet.vertex_ai_agent import VertexAIAgent
from pixel_planet.config import PROJECT_ID


def main():
    """Run a simple agent demo."""
    
    if PROJECT_ID == "your-gcp-project":
        print("❌ Please set GCP_PROJECT_ID environment variable or update config.py")
        print("   Example: export GCP_PROJECT_ID=my-project-123")
        return
    
    # Create agent (uses config defaults)
    print("\n🤖 Initializing Vertex AI Agent with BigQuery...\n")
    agent = VertexAIAgent()
    
    # Ask a simple question
    print("\n" + "="*70)
    print("Demo: Asking about data schema")
    print("="*70 + "\n")
    
    response = agent.ask(
        "What columns are in the weather table and what time range does the data cover?"
    )
    
    # Follow-up question (shows context retention)
    print("\n" + "="*70)
    print("Demo: Follow-up question with context")
    print("="*70 + "\n")
    
    response = agent.ask(
        "What was the highest temperature recorded and when did it occur?"
    )
    
    print("\n✅ Demo complete!")
    print("\nThe agent:")
    print("  ✓ Understood natural language questions")
    print("  ✓ Generated and executed BigQuery SQL")
    print("  ✓ Analyzed results and provided insights")
    print("  ✓ Maintained conversation context")


if __name__ == "__main__":
    main()

