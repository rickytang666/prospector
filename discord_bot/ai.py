import json
from google import genai
from discord_bot.config import GEMINI_API_KEY

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def get_contact_infos(candidates: list[dict]) -> list[dict]:
    """returns contact info for each candidate.
    website comes from canonical_url in the DB (reliable).
    contact_person is the only thing we ask the llm — just a department/role hint, not an email.
    we skip email entirely to avoid hallucinated addresses.
    """
    if not candidates:
        return []

    candidates = candidates[:10]

    # build entries using known data first
    entries = []
    for c in candidates:
        # canonical_url is stored in the DB, use it directly
        website = c.get("canonical_url") or c.get("website") or ""
        entries.append({"name": c.get("name", "Unknown"), "website": website})

    # only ask llm for contact department (this it can reasonably infer)
    names = [e["name"] for e in entries]
    prompt = f"""For each company below, name the most relevant team or department a university engineering design team should contact for sponsorship or technical support.
Keep it short — a job title or team name only (e.g. "University Partnerships", "Developer Relations", "Sponsorship Team").

Companies: {json.dumps(names)}

Return a JSON array with exactly {len(names)} strings in the same order. Return only valid JSON, no explanation."""

    try:
        response = await _get_client().aio.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        contact_persons = json.loads(text)
        if not isinstance(contact_persons, list):
            contact_persons = [""] * len(entries)
    except Exception as e:
        print(f"[ai] get_contact_infos failed: {e}")
        contact_persons = [""] * len(entries)

    return [
        {
            "name": e["name"],
            "contact_person": contact_persons[i] if i < len(contact_persons) else "",
            "contact_email": "",  # don't guess — hallucinated emails are worse than none
            "website": e["website"],
        }
        for i, e in enumerate(entries)
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
        response = await _get_client().aio.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        print(f"[ai] expand_recommended_ask failed: {e}")
        return ask
