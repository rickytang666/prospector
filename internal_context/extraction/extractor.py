import json
from openai import OpenAI
from config import OPENROUTER_API_KEY
from internal_context.models import Chunk

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MODEL = "google/gemini-2.5-flash-lite"
MAX_CHUNKS = 20
MAX_WORDS_PER_CHUNK = 200


def truncate(text: str, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")


def extract_team_context(team_name: str, chunks: list[Chunk]) -> dict:
    # prioritize readme/docs
    priority = [c for c in chunks if c.source_type in ("github_readme", "website", "notion")]
    rest = [c for c in chunks if c.source_type not in ("github_readme", "website", "notion")]
    selected = (priority + rest)[:MAX_CHUNKS]

    context_blob = "\n\n---\n\n".join(truncate(c.content, MAX_WORDS_PER_CHUNK) for c in selected)

    prompt = f"""You are analyzing a university engineering design team's documentation.

Here is their content (from github, website, docs):

{context_blob}

Return a JSON object with exactly these fields:
{{
  "tech_stack": ["list of specific tools, languages, frameworks, hardware they use"],
  "focus_areas": ["list of subsystems or problem areas they work on"],
  "blockers": ["list of things they are actively stuck on or struggling with"],
  "needs": ["list of types of support, tooling, or sponsors they would benefit from"]
}}

Be specific and concise. Each list should have 3-8 items. Return only valid JSON, no explanation."""

    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    raw = res.choices[0].message.content
    # print(f"raw llm output: {raw}")

    try:
        parsed = json.loads(raw)
    except Exception as e:
        print(f"failed to parse llm response for {team_name}: {e}")
        parsed = {}

    return {
        "team_name": team_name,
        "tech_stack": parsed.get("tech_stack", []),
        "focus_areas": parsed.get("focus_areas", []),
        "blockers": parsed.get("blockers", []),
        "needs": parsed.get("needs", []),
        "raw_llm_output": raw,
    }
