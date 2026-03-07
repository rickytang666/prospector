from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


async def insert_chunks(chunks: list[dict]) -> None:
    db = get_client()
    db.table("chunks").insert(chunks).execute()


async def get_chunks(team_name: str) -> list[dict]:
    db = get_client()
    res = db.table("chunks").select("*").eq("team_name", team_name).execute()
    return res.data
