import json
from google import genai
from discord_bot.config import GEMINI_API_KEY

_client = genai.Client(api_key=GEMINI_API_KEY)


async def get_contact_infos(candidates: list[dict]) -> list[dict]:
    """Batch Gemini call — returns contact info for each candidate in the same order.
    Each entry: {name, contact_person, contact_email, website}
    Capped at 10 to keep prompts manageable.
    """
    if not candidates:
        return []

    candidates = candidates[:10]
    names = [c.get("name", "Unknown") for c in candidates]
    prompt = f"""For each organization below, provide realistic contact information for a university engineering team seeking sponsorship or technical support.

Organizations: {json.dumps(names)}

Return a JSON array with exactly {len(names)} objects in the same order:
[
  {{
    "name": "...",
    "contact_person": "Job title or team name (e.g. 'Developer Relations Team', 'University Partnerships')",
    "contact_email": "Most likely contact email (e.g. 'university@company.com', 'sponsors@company.com')",
    "website": "Most relevant URL for university/student programs or partnerships"
  }}
]

Return only valid JSON, no explanation."""

    response = await _client.aio.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )

    try:
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        print(f"[ai] failed to parse contact infos: {e}")
        return [
            {"name": c.get("name", ""), "contact_person": "", "contact_email": "", "website": ""}
            for c in candidates
        ]


async def expand_recommended_ask(ask: str, entity_name: str, team_name: str) -> str:
    """Expands a brief recommended ask into exactly 3 professional sentences."""
    prompt = f"""Expand the following into exactly 3 clear, professional sentences that {team_name} could send to {entity_name}:

"{ask}"

Requirements:
- Exactly 3 sentences
- Professional and direct
- Written from the perspective of a university engineering design team seeking support
- Return only the 3 sentences, no labels or extra text"""

    try:
        response = await _client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"[ai] expand_recommended_ask failed: {e}")
        return ask
