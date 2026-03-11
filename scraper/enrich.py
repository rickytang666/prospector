import json
import os
import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv


def _stable_id(name: str) -> str:
    """deterministic uuid from company name — same name always → same id.
    this lets upsert correctly overwrite existing rows on re-runs."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name.lower().strip()))

load_dotenv()

data_dir = Path("data")
raw_dir = data_dir / "raw_pages"
companies_file = data_dir / "companies.json"
entities_file = data_dir / "entities.json"

# cheap model
ENRICH_MODEL = "meta-llama/llama-3.1-8b-instruct"

VERTICAL_TAGS = {
    "aerospace": ["aerospace", "satellite", "space", "rocketry", "avionics"],
    "spaceflight": ["aerospace", "space", "rocketry", "satellite"],
    "automotive": ["automotive", "embedded", "hardware", "powertrain", "manufacturing"],
    "electric_vehicles": ["ev", "automotive", "battery", "power-systems", "embedded"],
    "autonomous_vehicles": ["autonomous", "robotics", "sensors", "computer-vision", "software"],
    "semiconductors": ["semiconductors", "embedded", "electronics", "hardware", "fpga"],
    "sensors": ["sensors", "hardware", "measurement", "embedded"],
    "lidar": ["lidar", "sensors", "mapping", "autonomous"],
    "robotics": ["robotics", "embedded", "automation", "hardware"],
    "cloud": ["cloud", "infrastructure", "compute", "software"],
    "simulation": ["simulation", "cad", "fea", "engineering-tools", "software"],
    "manufacturing": ["manufacturing", "pcb", "hardware", "prototyping", "machining"],
    "ai_hardware": ["ai", "gpu", "ml", "hardware", "compute"],
    "defense": ["defense", "aerospace", "systems-engineering", "embedded", "communications"],
    "power_systems": ["power-systems", "energy", "embedded", "hardware", "battery"],
    "telecommunications": ["communications", "rf", "embedded", "wireless"],
    "eda_tools": ["eda", "pcb", "fpga", "electronics", "semiconductors"],
    "industrial_automation": ["automation", "robotics", "plc", "hardware", "embedded"],
    "avionics": ["avionics", "aerospace", "embedded", "communications", "hardware"],
    "test_equipment": ["test-equipment", "electronics", "hardware", "measurement"],
    "connectors": ["hardware", "electronics", "connectors", "manufacturing"],
    "engineering": ["engineering", "hardware", "systems-engineering", "software"],
    "engineering_consulting": ["engineering", "systems-engineering", "consulting"],
    "developer_tools": ["developer-tools", "software", "embedded", "cloud"],
    # canada-specific verticals from wikidata
    "canada_tech": ["software", "engineering", "embedded", "hardware"],
    "canada_engineering": ["engineering", "hardware", "systems-engineering", "manufacturing"],
    "canada_aerospace": ["aerospace", "satellite", "space", "avionics"],
    "canada_software": ["software", "embedded", "developer-tools"],
    "canada_automotive": ["automotive", "ev", "embedded", "manufacturing"],
    "canada_robotics": ["robotics", "embedded", "automation", "hardware"],
    "canada_defense": ["defense", "embedded", "systems-engineering", "communications"],
}

SOURCE_SUPPORT = {
    "design_team_sponsor": ["sponsorship", "financial_support"],
    "velocity_startup": ["technical_mentorship", "developer_tools"],
    "engineering_competition_sponsor": ["sponsorship", "technical_mentorship"],
    "wikidata_vertical": ["sponsorship"],
    "hardcoded_seed": ["sponsorship", "software_credits"],
}

# keyword → tag for companies with no vertical (design team sponsors etc.)
NAME_TAGS = {
    "aero": "aerospace", "space": "aerospace", "flight": "aerospace", "rocket": "aerospace",
    "orbital": "aerospace", "launch": "aerospace", "satellite": "aerospace",
    "robot": "robotics", "auto": "automotive", "electric": "electric_vehicles",
    "solar": "power-systems", "sensor": "sensors", "lidar": "lidar",
    "semi": "semiconductors", "chip": "semiconductors", "circuit": "electronics",
    "pcb": "pcb", "embed": "embedded", "firmware": "embedded", "fpga": "fpga",
    "soft": "software", "cloud": "cloud", "data": "software",
    "power": "power-systems", "energy": "power-systems", "battery": "power-systems",
    "defense": "defense", "defence": "defense",
    "mfg": "manufacturing", "manufactur": "manufacturing",
    "cad": "cad", "simul": "simulation",
    "rf": "rf", "wireless": "communications", "antenna": "rf",
    "optim": "software", "analyt": "software",
}


def get_affinity(company):
    src_type = company.get("source_type", "")
    evidence = []

    if src_type == "design_team_sponsor":
        source_teams = company.get("source_teams") or []
        if source_teams:
            for st in source_teams:
                evidence.append({
                    "type": "team_sponsor",
                    "text": f"Listed as sponsor for {st['team']}",
                    "source_url": st.get("source_url", ""),
                })
        else:
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
    elif src_type == "engineering_competition_sponsor":
        assoc = company.get("association", "an engineering competition")
        evidence.append({
            "type": "competition_sponsor",
            "text": f"Sponsor of {assoc} — explicitly supports student engineering teams",
            "source_url": company.get("source_url", ""),
        })
    elif src_type == "wikidata_vertical":
        vertical = company.get("vertical", "engineering")
        evidence.append({
            "type": "industry_vertical",
            "text": f"Active company in {vertical.replace('_', ' ')} industry",
            "source_url": company.get("source_url", ""),
        })
    elif src_type == "hardcoded_seed":
        vertical = company.get("vertical", "engineering")
        evidence.append({
            "type": "known_engineering_company",
            "text": f"Known engineering/tech company in {vertical.replace('_', ' ')} sector",
            "source_url": company.get("url", ""),
        })

    return evidence


def _slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("/", "_").replace(".", "")[:50]


def _tags_from_vertical(vertical: str) -> list[str]:
    return list(VERTICAL_TAGS.get(vertical, []))


def _tags_from_name(name: str) -> list[str]:
    """keyword match on company name — last resort when no vertical or text available."""
    name_lower = name.lower()
    found = set()
    for kw, tag in NAME_TAGS.items():
        if kw in name_lower:
            found.add(tag)
    return list(found)


def _make_template_summary(company: dict) -> str:
    name = company["name"]
    src_type = company.get("source_type", "")
    teams = company.get("source_teams", [])
    vertical = company.get("vertical", "")

    if src_type == "design_team_sponsor" and teams:
        team_names = [t["team"] for t in teams[:3]]
        suffix = f" in the {vertical.replace('_', ' ')} sector" if vertical else ""
        return f"{name} sponsors Waterloo design teams including {', '.join(team_names)}{suffix}."

    if src_type == "design_team_sponsor":
        team = company.get("team", "a Waterloo design team")
        return f"{name} is a sponsor of {team}."

    if src_type == "velocity_startup":
        return f"{name} is a startup from the Velocity incubator at the University of Waterloo."

    if vertical:
        return f"{name} is a company in the {vertical.replace('_', ' ')} sector."

    return f"{name} is a technology or engineering company."


def _get_llm_client():
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    except Exception:
        return None


def _llm_enrich(name: str, text: str, client) -> dict:
    """call llama 8b to get summary + tags from scraped text. very cheap."""
    prompt = f"""Company: {name}
Website text: {text[:2000]}

Write a 1-2 sentence description of what this company does and list 4-6 relevant engineering tags.
Tags should be specific and from areas like: aerospace, embedded, robotics, automotive, sensors, simulation, power-systems, pcb, manufacturing, hardware, software, ai, cloud, defense, rf, fpga, lidar, materials, structural.

JSON only, no markdown: {{"summary": "...", "tags": ["..."]}}"""

    try:
        resp = client.chat.completions.create(
            model=ENRICH_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=200,
        )
        raw = json.loads(resp.choices[0].message.content)
        return {
            "summary": str(raw.get("summary", "")).strip(),
            "tags": [str(t).strip().lower() for t in (raw.get("tags") or []) if str(t).strip()],
        }
    except Exception as e:
        print(f"    llm failed: {e}")
        return {"summary": "", "tags": []}


def _load_scraped_text(name: str) -> str:
    pages_file = raw_dir / _slug(name) / "pages.json"
    if not pages_file.exists():
        return ""
    with open(pages_file) as f:
        pages = json.load(f)
    return "\n\n".join(p["raw_text"] for p in pages.values() if p.get("raw_text"))


def enrich(limit=None, max_workers=10):
    """build entities.json from companies.json.

    priority order for summary:
    1. wikipedia extract (free, high quality for major companies)
    2. scraped homepage text → llama 8b concurrent (cheap, ~$0.01 total, ~2 min for 500)
    3. template string (free, works for everything else)

    llm calls run concurrently via threadpool — 10x faster than sequential.
    """
    with open(companies_file) as f:
        companies = json.load(f)
    if limit:
        companies = companies[:limit]

    # resume — skip already-enriched companies by name
    enriched_names: set[str] = set()
    entities: list[dict] = []
    if entities_file.exists():
        with open(entities_file) as f:
            existing = json.load(f)
        if isinstance(existing, list):
            entities = existing
            # only skip entities that already have a real summary — empty ones get another pass
            enriched_names = {e["name"] for e in entities if e.get("summary")}
    if enriched_names:
        print(f"resuming: {len(enriched_names)} have summary, {len(companies) - len(enriched_names)} to process")

    todo = [c for c in companies if c["name"] not in enriched_names]
    if not todo:
        print("all companies already enriched")
        return

    llm_client = _get_llm_client()
    if llm_client:
        print(f"llm ready ({ENRICH_MODEL}), concurrent workers={max_workers}")
    else:
        print("no openrouter key, using template summaries for all")

    # pass 1: split into paths — wiki / llm / template
    wiki_batch = []
    llm_batch = []   # (company, scraped_text)
    template_batch = []

    for company in todo:
        if company.get("wikipedia_extract"):
            wiki_batch.append(company)
        else:
            text = _load_scraped_text(company["name"])
            if text and llm_client:
                llm_batch.append((company, text))
            else:
                template_batch.append(company)

    print(f"paths: {len(wiki_batch)} wikipedia, {len(llm_batch)} llm, {len(template_batch)} template")

    # pass 2: run llm batch concurrently
    llm_results: dict[str, dict] = {}
    if llm_batch:
        print(f"firing {len(llm_batch)} concurrent llm calls...")
        t0 = time.time()

        def _call(item):
            company, text = item
            return company["name"], _llm_enrich(company["name"], text, llm_client)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_call, item): item[0]["name"] for item in llm_batch}
            done = 0
            for future in as_completed(futures):
                name, result = future.result()
                llm_results[name] = result
                done += 1
                if done % 20 == 0 or done == len(llm_batch):
                    print(f"  llm: {done}/{len(llm_batch)} done")

        elapsed = time.time() - t0
        print(f"llm batch done in {elapsed:.1f}s")

    # pass 3: build entities in original order
    def _build(company):
        name = company["name"]
        src_type = company.get("source_type", "")
        vertical = company.get("vertical", "")

        if company.get("wikipedia_extract"):
            summary = company["wikipedia_extract"]
            tags = _tags_from_vertical(vertical)
        elif name in llm_results:
            result = llm_results[name]
            # fall back to template if llm returned empty (failed calls)
            summary = result["summary"] or _make_template_summary(company)
            tags = result["tags"] or _tags_from_vertical(vertical) or _tags_from_name(name)
        else:
            summary = _make_template_summary(company)
            tags = _tags_from_vertical(vertical) or _tags_from_name(name)

        return {
            "id": _stable_id(name),
            "name": name,
            "entity_type": "provider",
            "canonical_url": company.get("url"),
            "summary": summary,  # always a string now — template is the final fallback
            "source_urls": [company.get("source_url", "")],
            "tags": tags,
            "support_types": SOURCE_SUPPORT.get(src_type, []),
            "waterloo_affinity_evidence": get_affinity(company),
            "contact_routes": [],
        }

    new_entities = [_build(c) for c in todo]
    # replace existing entries for re-processed companies, append new ones
    by_name = {e["name"]: e for e in entities}
    for e in new_entities:
        by_name[e["name"]] = e
    entities = list(by_name.values())

    with open(entities_file, "w") as f:
        json.dump(entities, f, indent=2)
    print(f"\ndone. {len(entities)} total entities saved. llm calls: {len(llm_results)}")


def fast_enrich(limit=None):
    """zero llm — wikipedia extracts + template summaries. runs in seconds. useful for testing."""
    with open(companies_file) as f:
        companies = json.load(f)
    if limit:
        companies = companies[:limit]

    enriched_names: set[str] = set()
    entities: list[dict] = []
    if entities_file.exists():
        with open(entities_file) as f:
            existing = json.load(f)
        if isinstance(existing, list):
            entities = existing
            enriched_names = {e["name"] for e in entities}
    if enriched_names:
        print(f"resuming: {len(enriched_names)} already done")

    todo = [c for c in companies if c["name"] not in enriched_names]
    for company in todo:
        name = company["name"]
        src_type = company.get("source_type", "")
        vertical = company.get("vertical", "")

        wiki_extract = company.get("wikipedia_extract", "")
        if wiki_extract:
            summary = wiki_extract
            tags = _tags_from_vertical(vertical)
        else:
            summary = _make_template_summary(company)
            tags = _tags_from_vertical(vertical) or _tags_from_name(name)

        print(f"  {name}")
        entities.append({
            "id": _stable_id(name),
            "name": name,
            "entity_type": "provider",
            "canonical_url": company.get("url"),
            "summary": summary,
            "source_urls": [company.get("source_url", "")],
            "tags": tags,
            "support_types": SOURCE_SUPPORT.get(src_type, []),
            "waterloo_affinity_evidence": get_affinity(company),
            "contact_routes": [],
        })

    with open(entities_file, "w") as f:
        json.dump(entities, f, indent=2)
    print(f"\ndone. {len(entities)} entities saved to {entities_file}")


if __name__ == "__main__":
    import sys
    if "--fast" in sys.argv:
        fast_enrich()
    else:
        enrich()
