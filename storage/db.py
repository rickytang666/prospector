import asyncio
import threading
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Thread-local client: each thread gets its own instance so asyncio.to_thread
# calls don't share a single httpx connection pool (which caused hangs).
_local = threading.local()


def _get_client() -> Client:
    if not hasattr(_local, "client"):
        _local.client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _local.client


async def get_existing_hashes(team_name: str) -> dict[str, str]:
    def _run():
        c = _get_client()
        res = c.table("chunks").select("id, content_hash").eq("team_name", team_name).execute()
        return {row["content_hash"]: row["id"] for row in res.data if row.get("content_hash")}
    return await asyncio.to_thread(_run)


async def delete_chunks(team_name: str) -> None:
    def _run():
        c = _get_client()
        c.table("chunks").delete().eq("team_name", team_name).execute()
    await asyncio.to_thread(_run)


async def delete_chunks_by_ids(ids: list[str]) -> None:
    if not ids:
        return
    def _run():
        c = _get_client()
        c.table("chunks").delete().in_("id", ids).execute()
    await asyncio.to_thread(_run)


async def insert_chunks(chunks: list) -> None:
    rows = [c.model_dump(exclude_none=True) for c in chunks]
    def _run():
        c = _get_client()
        c.table("chunks").insert(rows).execute()
    await asyncio.to_thread(_run)


async def upsert_team_context(data: dict) -> None:
    def _run():
        c = _get_client()
        c.table("team_context").upsert(data, on_conflict="team_name").execute()
    await asyncio.to_thread(_run)


async def get_team_context(team_name: str) -> dict | None:
    def _run():
        c = _get_client()
        res = c.table("team_context").select("*").eq("team_name", team_name).maybe_single().execute()
        return res.data
    return await asyncio.to_thread(_run)


async def delete_team_context(team_name: str) -> None:
    db = get_client()
    db.table("team_context").delete().eq("team_name", team_name).execute()


async def delete_team(guild_id: str, team_name: str) -> None:
    """Remove team row from teams table (after nuke)."""
    db = get_client()
    db.table("teams").delete().eq("guild_id", str(guild_id)).eq("team_name", team_name).execute()


async def get_chunks(team_name: str) -> list[dict]:
    db = get_client()
    res = db.table("chunks").select("id, team_name, source_type, source_url, content, created_at").eq("team_name", team_name).execute()
    return res.data or []


# ---- teams (setup-team: register team per guild) ----
async def list_teams(guild_id: str) -> list[dict]:
    db = get_client()
    res = db.table("teams").select("*").eq("guild_id", str(guild_id)).execute()
    return res.data or []


async def upsert_team(guild_id: str, team_name: str, repo_url: str | None = None) -> None:
    db = get_client()
    row = {"guild_id": str(guild_id), "team_name": team_name, "repo_url": repo_url or ""}
    db.table("teams").upsert(row, on_conflict="guild_id,team_name").execute()


# ---- user_teams (configure-team: assign user to a team) ----
async def get_user_team(guild_id: str, user_id: str) -> str | None:
    db = get_client()
    res = db.table("user_teams").select("team_name").eq("guild_id", str(guild_id)).eq("user_id", str(user_id)).maybe_single().execute()
    if res.data and isinstance(res.data, dict):
        return res.data.get("team_name")
    return None


async def set_user_team(guild_id: str, user_id: str, team_name: str) -> None:
    db = get_client()
    db.table("user_teams").upsert(
        {"guild_id": str(guild_id), "user_id": str(user_id), "team_name": team_name},
        on_conflict="guild_id,user_id",
    ).execute()


async def remove_user_team(guild_id: str, user_id: str) -> None:
    db = get_client()
    db.table("user_teams").delete().eq("guild_id", str(guild_id)).eq("user_id", str(user_id)).execute()


async def remove_user_teams_for_team(guild_id: str, team_name: str) -> None:
    """Remove all user associations for a team (e.g. after nuke)."""
    db = get_client()
    db.table("user_teams").delete().eq("guild_id", str(guild_id)).eq("team_name", team_name).execute()


async def get_team_context_for_user(guild_id: str, user_id: str) -> dict | None:
    """Build full team context dict for a user (their assigned team). Returns None if no assignment."""
    team_name = await get_user_team(guild_id, user_id)
    if not team_name:
        return None
    stored = await get_team_context(team_name)
    if not stored:
        return None
    teams = await list_teams(guild_id)
    repo_url = ""
    for t in teams:
        if (t.get("team_name") or "").strip() == team_name.strip():
            repo_url = t.get("repo_url") or ""
            break
    blockers = stored.get("blockers") or []
    return {
        "team_name": team_name,
        "repo": repo_url,
        "repo_url": repo_url,
        "subsystems": stored.get("focus_areas") or [],
        "tech_stack": stored.get("tech_stack") or [],
        "blockers": blockers,
        "active_blockers": [{"summary": b, "tags": [], "severity": "medium"} for b in blockers],
        "inferred_support_needs": stored.get("needs") or [],
        "context_summary": stored.get("raw_llm_output") or "",
    }


# ---- remove_from_memory: find chunks by query (keyword match) and delete ----
def _escape_like(s: str) -> str:
    """Escape % and _ for use in SQL LIKE."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def find_chunk_ids_by_query(team_name: str, query: str, limit: int = 20) -> list[str]:
    """Return chunk ids whose content contains the query (case-insensitive)."""
    db = get_client()
    pattern = f"%{_escape_like(query)}%"
    res = db.table("chunks").select("id").eq("team_name", team_name).ilike("content", pattern).limit(limit).execute()
    return [r["id"] for r in (res.data or []) if r.get("id")]
