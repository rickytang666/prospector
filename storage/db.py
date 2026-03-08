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


async def get_chunks(team_name: str) -> list[dict]:
    def _run():
        c = _get_client()
        res = c.table("chunks").select("id, team_name, source_type, source_url, content, created_at").eq("team_name", team_name).execute()
        return res.data
    return await asyncio.to_thread(_run)