import asyncio
import json
import os
from openai import AsyncOpenAI
from discord_bot.email_finder import find_email

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

    # find emails concurrently — scrape contact pages + mx-validated prefix fallback
    email_results = await asyncio.gather(
        *[asyncio.to_thread(find_email, e["website"]) for e in entries]
    )

    return [
        {
            "name": e["name"],
            "contact_person": contact_persons[i] if i < len(contact_persons) else "",
            "contact_email": email_results[i][0],
            "contact_email_verified": email_results[i][1],  # true = found on site, false = suggested
            "website": e["website"],
        }
        for i, e in enumerate(entries)
    ]


async def generate_email(team_context: dict, organization: str, email_type: str, matched_reason: str = "") -> str:
    """Draft a cold sponsorship/outreach email. matched_reason gives company-specific context."""
    team_name = team_context["team_name"]
    subsystems = ", ".join((team_context.get("subsystems") or [])[:3])
    tech = ", ".join((team_context.get("tech_stack") or [])[:3])
    website = team_context.get("website_url") or ""
    repo = team_context.get("repo_url") or team_context.get("repo") or ""
    sig_link = website or repo  # prefer official website over github
    company_context = f"Why this company fits: {matched_reason}" if matched_reason else ""

    prompt = f"""Write a cold {email_type} email from the university engineering design team "{team_name}" to {organization}.

Team info:
- Team name (use exactly as written): {team_name}
- Key subsystems: {subsystems}
- Tech: {tech}
{f"- Website: {sig_link}" if sig_link else ""}
{company_context}

Tone: written by a real university student — genuine and respectful, but not stiff or corporate. No buzzwords, no "I hope this email finds you well", no "leverage", no "synergy", no "ideal partner". Write like a sharp student who did their homework on {organization}, not like a PR department.

Requirements:
- Length: 150-200 words
- First line must be "Subject: <subject line>"
- Do NOT mention the team's internal struggles or documentation problems
- Pick 1-2 specific things about {organization} to reference from the context above — show you actually know what they do
- End with one clear ask (hardware loan, software license, monetary sponsorship, etc.) and a low-friction next step ("happy to jump on a call" or similar)
- Signature: {team_name}{f", {sig_link}" if sig_link else ""}
- No placeholders — write a complete, sendable draft"""

    resp = await _get_client().chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    return (resp.choices[0].message.content or "").strip()


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
