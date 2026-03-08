from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


async def get_existing_hashes(team_name: str) -> dict[str, str]:
    """returns {content_hash: chunk_id} for all chunks of a team"""
    db = get_client()
    res = db.table("chunks").select("id, content_hash").eq("team_name", team_name).execute()
    return {row["content_hash"]: row["id"] for row in res.data if row.get("content_hash")}


async def delete_chunks_by_ids(ids: list[str]) -> None:
    if not ids:
        return
    db = get_client()
    db.table("chunks").delete().in_("id", ids).execute()


async def insert_chunks(chunks: list) -> None:
    db = get_client()
    rows = [c.model_dump(exclude_none=True) for c in chunks]
    db.table("chunks").insert(rows).execute()


async def upsert_team_context(data: dict) -> None:
    db = get_client()
    db.table("team_context").upsert(data, on_conflict="team_name").execute()


async def get_team_context(team_name: str) -> dict | None:
    db = get_client()
    res = db.table("team_context").select("*").eq("team_name", team_name).maybe_single().execute()
    return res.data


async def get_chunks(team_name: str) -> list[dict]:
    db = get_client()
    res = db.table("chunks").select("id, team_name, source_type, source_url, content, created_at").eq("team_name", team_name).execute()
    return res.data
