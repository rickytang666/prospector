import json
import os
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

load_dotenv()

# Throttle and retry to avoid Gemini 429 rate limits
ENRICH_DELAY_SECONDS = float(os.environ.get("ENRICH_DELAY_SECONDS", "1.5"))
ENRICH_MAX_RETRIES = int(os.environ.get("ENRICH_MAX_RETRIES", "5"))

data_dir = Path("data")
raw_dir = data_dir / "raw_pages"
companies_file = data_dir / "companies.json"
entities_file = data_dir / "entities.json"

#prompt
extraction_prompt = """Given this scraped text from a company's website, extract structured info.

Company name: {name}

Scraped content:
{content}

Return JSON with these fields:
- summary: 1-2 sentence description of what this company does
- tags: list of relevant tech/industry tags (lowercase, e.g. "geospatial", "cloud", "robotics")
- support_types: what kind of support they could offer a student engineering team. pick from: software_credits, hardware_donation, technical_mentorship, sponsorship, api_access, cloud_credits, tooling, developer_tools, other
- contact_type: one of "contact_page", "email", "partnership_page", or null
- contact_value: email or url if found, else null"""


def get_affinity(company):
    src_type = company.get("source_type", "")
    evidence = []

    if src_type == "design_team_sponsor":
        team = company.get("team", "a Waterloo design team")
        evidence.append({
            "type": "team_sponsor",
            "text": f"Listed as sponsor for {team}",
            "source_url": company.get("source_url", ""),
        })
    elif src_type == "velocity_startup":
        evidence.append({
            "type": "startup_incubator",
            "text": "Velocity incubator company (University of Waterloo)",
            "source_url": company.get("source_url", ""),
        })
    elif src_type == "yc_startup":
        evidence.append({
            "type": "yc_company",
            "text": "Y Combinator company",
            "source_url": company.get("source_url", ""),
        })

    return evidence



def _generate_with_retry(client, prompt_text):
    """Call Gemini with retries on 429 (rate limit)."""
    last_err = None
    for attempt in range(ENRICH_MAX_RETRIES):
        try:
            return client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt_text,
                config={"response_mime_type": "application/json"},
            )
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            last_err = e
            code = getattr(e, "code", None)
            is_rate_limit = code == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < ENRICH_MAX_RETRIES - 1:
                wait = (2 ** attempt) + 1  # 2, 3, 5, 9, 17 sec
                print(f"  rate limited (429), waiting {wait}s before retry {attempt + 2}/{ENRICH_MAX_RETRIES}...")
                time.sleep(wait)
            else:
                raise
    raise last_err


def build_entity(company, scraped_text, client):
    resp = _generate_with_retry(
        client,
        extraction_prompt.format(name=company["name"], content=scraped_text[:30000]),
    )

    try:
        raw = json.loads(resp.text)
        # LLM sometimes returns a list (e.g. single-item array); normalize to dict
        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], dict):
            extracted = raw[0]
        elif isinstance(raw, dict):
            extracted = raw
        else:
            extracted = {}
    except Exception:
        print(f"  llm parse failed for {company['name']}")
        extracted = {}

    contact_routes = []
    contact_type = extracted.get("contact_type", "contact_page") or "contact_page"
    contact_value = extracted.get("contact_value")
    if contact_value:
        # support single string or list of strings
        values = contact_value if isinstance(contact_value, list) else [contact_value]
        for v in values:
            if v and isinstance(v, str):
                contact_routes.append({"type": contact_type, "value": v})

    tags = extracted.get("tags", [])
    support_types = extracted.get("support_types", [])
    if not isinstance(tags, list):
        tags = []
    if not isinstance(support_types, list):
        support_types = []

    #build entity
    return {
        "id": str(uuid.uuid4()),
        "name": company["name"],
        "entity_type": "provider",
        "canonical_url": company.get("url"),
        "summary": extracted.get("summary"),
        "source_urls": [company.get("source_url", "")],
        "tags": tags,
        "support_types": support_types,
        "waterloo_affinity_evidence": get_affinity(company),
        "contact_routes": contact_routes,
    }


#helper for file paths
def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]

#enrich to entities.json
def enrich(limit=None):
    with open(companies_file) as f:
        companies = json.load(f)
    if limit:
        companies = companies[:limit]

    # Resume: load existing entities so we don't re-do work after a crash
    if entities_file.exists():
        with open(entities_file) as f:
            entities = json.load(f)
        if not isinstance(entities, list):
            entities = []
    else:
        entities = []
    start_index = len(entities)
    if start_index > 0:
        print(f"Resuming from company {start_index + 1}/{len(companies)} (found {start_index} existing entities)")

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    for i in range(start_index, len(companies)):
        company = companies[i]
        name = company["name"]
        s = slug(name)
        pages_file = raw_dir / s / "pages.json"

        scraped_text = ""
        if pages_file.exists():
            with open(pages_file) as f:
                pages = json.load(f)
            scraped_text = "\n\n".join(p["raw_text"] for p in pages.values() if p.get("raw_text"))

        if not scraped_text:
            print(f"[{i+1}/{len(companies)}] {name} - no scraped content, basic entity")
            entities.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "entity_type": "provider",
                "canonical_url": company.get("url"),
                "source_urls": [company.get("source_url", "")],
                "waterloo_affinity_evidence": get_affinity(company),
                "tags": [],
                "support_types": [],
                "contact_routes": [],
            })
            with open(entities_file, "w") as f:
                json.dump(entities, f, indent=2)
            continue

        print(f"[{i+1}/{len(companies)}] {name} - enriching...")
        entity = build_entity(company, scraped_text, client)
        entities.append(entity)
        # Throttle to avoid Gemini 429; skip delay on last item
        if i < len(companies) - 1 and ENRICH_DELAY_SECONDS > 0:
            time.sleep(ENRICH_DELAY_SECONDS)
        # Checkpoint so we can resume after a crash
        with open(entities_file, "w") as f:
            json.dump(entities, f, indent=2)

    print(f"\nsaved {len(entities)} entities to {entities_file}")


if __name__ == "__main__":
    enrich()

