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
        c.table("team_context").delete().eq("team_name", data["team_name"]).execute()
        c.table("team_context").insert(data).execute()
    await asyncio.to_thread(_run)


async def get_team_context(team_name: str) -> dict | None:
    def _run():
        c = _get_client()
        res = c.table("team_context").select("*").eq("team_name", team_name).limit(1).execute()
        return res.data[0] if res.data else None
    return await asyncio.to_thread(_run)


async def delete_team_context(team_name: str) -> None:
    def _run():
        c = _get_client()
        c.table("team_context").delete().eq("team_name", team_name).execute()
    await asyncio.to_thread(_run)


async def delete_team(guild_id: str, team_name: str) -> None:
    """Remove team row from teams table (after nuke)."""
    def _run():
        c = _get_client()
        c.table("teams").delete().eq("guild_id", str(guild_id)).eq("team_name", team_name).execute()
    await asyncio.to_thread(_run)


async def get_chunks(team_name: str) -> list[dict]:
    def _run():
        c = _get_client()
        res = c.table("chunks").select("id, team_name, source_type, source_url, content, created_at").eq("team_name", team_name).execute()
        return res.data or []
    return await asyncio.to_thread(_run)


# ---- teams (setup-team: register team per guild) ----
async def list_teams(guild_id: str) -> list[dict]:
    def _run():
        c = _get_client()
        res = c.table("teams").select("*").eq("guild_id", str(guild_id)).execute()
        return res.data or []
    return await asyncio.to_thread(_run)


async def upsert_team(guild_id: str, team_name: str, repo_url: str | None = None) -> None:
    def _run():
        c = _get_client()
        row = {"guild_id": str(guild_id), "team_name": team_name, "repo_url": repo_url or ""}
        c.table("teams").upsert(row, on_conflict="guild_id,team_name").execute()
    await asyncio.to_thread(_run)


# ---- user_teams (multiple teams per user; one "active" for context) ----
async def get_user_teams(guild_id: str, user_id: str) -> list[dict]:
    """All teams this user is in; each dict has team_name, is_active."""
    def _run():
        c = _get_client()
        res = c.table("user_teams").select("team_name, is_active").eq("guild_id", str(guild_id)).eq("user_id", str(user_id)).execute()
        rows = res.data or []
        out = []
        for r in rows:
            if isinstance(r, dict) and r.get("team_name"):
                out.append({"team_name": r["team_name"], "is_active": r.get("is_active", True)})
        return out
    return await asyncio.to_thread(_run)


async def get_user_team(guild_id: str, user_id: str) -> str | None:
    """Active team for context (is_active=true), or first team if no is_active column / single team."""
    teams = await get_user_teams(guild_id, user_id)
    if not teams:
        return None
    active = [t["team_name"] for t in teams if t.get("is_active", True)]
    return active[0] if active else teams[0]["team_name"]


async def set_user_team(guild_id: str, user_id: str, team_name: str) -> None:
    """Add (or re-add) user to team and set it as active."""
    def _run():
        c = _get_client()
        g, u, n = str(guild_id), str(user_id), team_name.strip()
        c.table("user_teams").upsert(
            {"guild_id": g, "user_id": u, "team_name": n, "is_active": True},
            on_conflict="guild_id,user_id,team_name",
        ).execute()
        others = c.table("user_teams").select("id").eq("guild_id", g).eq("user_id", u).neq("team_name", n).execute()
        for row in (others.data or []):
            if row.get("id"):
                c.table("user_teams").update({"is_active": False}).eq("id", row["id"]).execute()
    await asyncio.to_thread(_run)


async def set_active_team(guild_id: str, user_id: str, team_name: str) -> None:
    """Set which team is active for this user (must already be in the team)."""
    def _run():
        c = _get_client()
        g, u, n = str(guild_id), str(user_id), team_name.strip()
        c.table("user_teams").update({"is_active": False}).eq("guild_id", g).eq("user_id", u).execute()
        c.table("user_teams").update({"is_active": True}).eq("guild_id", g).eq("user_id", u).eq("team_name", n).execute()
    await asyncio.to_thread(_run)


async def remove_user_team(guild_id: str, user_id: str, team_name: str | None = None) -> None:
    """Remove one membership (if team_name given) or all memberships for this user."""
    def _run():
        c = _get_client()
        q = c.table("user_teams").delete().eq("guild_id", str(guild_id)).eq("user_id", str(user_id))
        if team_name:
            q = q.eq("team_name", team_name.strip())
        q.execute()
    await asyncio.to_thread(_run)


async def remove_user_teams_for_team(guild_id: str, team_name: str) -> None:
    """Remove all user associations for a team (e.g. after nuke)."""
    def _run():
        c = _get_client()
        c.table("user_teams").delete().eq("guild_id", str(guild_id)).eq("team_name", team_name).execute()
    await asyncio.to_thread(_run)


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
    def _run():
        c = _get_client()
        pattern = f"%{_escape_like(query)}%"
        res = c.table("chunks").select("id").eq("team_name", team_name).ilike("content", pattern).limit(limit).execute()
        return [r["id"] for r in (res.data or []) if r.get("id")]
    return await asyncio.to_thread(_run)
