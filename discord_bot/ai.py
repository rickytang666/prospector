import json
import os
from openai import AsyncOpenAI

_client = None

def _get_client():
    global _client
    if _client is None:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        _client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    return _client

_MODEL = "google/gemini-2.5-flash-lite"


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

Return JSON: {{"contacts": ["dept name", ...]}} with exactly {len(names)} strings in the same order."""

    try:
        resp = await _get_client().chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        parsed = json.loads(resp.choices[0].message.content)
        # model may return {"contacts": [...]} or just [...]
        contact_persons = parsed if isinstance(parsed, list) else parsed.get("contacts", parsed.get("result", []))
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
        resp = await _get_client().chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[ai] expand_recommended_ask failed: {e}")
        return ask
