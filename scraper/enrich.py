import json
import os
import uuid
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv()

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



def build_entity(company, scraped_text, client):
    resp = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=extraction_prompt.format(name=company["name"], content=scraped_text[:30000]),
        config={"response_mime_type": "application/json"},
    )

    try:
        extracted = json.loads(resp.text)
    except:
        print(f"  llm parse failed for {company['name']}")
        extracted = {}

    contact_routes = []
    if extracted.get("contact_value"):
        contact_routes.append({
            "type": extracted.get("contact_type", "contact_page"),
            "value": extracted["contact_value"],
        })

    #build entity
    return {
        "id": str(uuid.uuid4()),
        "name": company["name"],
        "entity_type": "provider",
        "canonical_url": company.get("url"),
        "summary": extracted.get("summary"),
        "source_urls": [company.get("source_url", "")],
        "tags": extracted.get("tags", []),
        "support_types": extracted.get("support_types", []),
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

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    entities = []

    for i, company in enumerate(companies):
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
            continue

        print(f"[{i+1}/{len(companies)}] {name} - enriching...")
        entity = build_entity(company, scraped_text, client)
        entities.append(entity)

    with open(entities_file, "w") as f:
        json.dump(entities, f, indent=2)
    print(f"\nsaved {len(entities)} entities to {entities_file}")


if __name__ == "__main__":
    enrich()

