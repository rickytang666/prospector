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
