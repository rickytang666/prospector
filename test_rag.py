import asyncio
import json
import os
import sys

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from discord_bot.testing_info import MOCK_TEAM_CONTEXT
from retrieval.api import find_providers_dict

async def main():
    print("Testing RAG: find_providers_dict")
    query = "We need chips that are powerful for gpu computing."
    
    print(f"Query: {query}")
    print("Team Context:", json.dumps(MOCK_TEAM_CONTEXT, indent=2))
    
    result = await asyncio.to_thread(
        find_providers_dict,
        team_context=MOCK_TEAM_CONTEXT,
        query=query,
        k=3
    )
    
    print("\n--- RAG Results ---")
    candidates = result.get("candidates", [])
    for idx, c in enumerate(candidates):
        print(f"\n[{idx+1}] {c.get('name')} (Score: {c.get('overall_score')})")
        print("Reasons:")
        for r in c.get('matched_reasons', []):
            print(f" - {r}")
            
    if result.get("retrieval_metadata"):
        print("\nRetrieval Metadata:")
        print(json.dumps(result["retrieval_metadata"], indent=2))

if __name__ == "__main__":
    asyncio.run(main())
