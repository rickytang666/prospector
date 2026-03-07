import asyncpg
from config import DATABASE_URL

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool


async def save_team_context(ctx: dict) -> None:
    pool = await get_pool()
    # TODO: upsert into team_context
    pass


async def save_chunks(chunks: list[dict]) -> None:
    pool = await get_pool()
    # TODO: bulk insert, skip duplicates by chunk_id
    pass


async def get_team_context(team_name: str) -> dict | None:
    pool = await get_pool()
    # TODO
    return None


async def get_chunks(team_name: str) -> list[dict]:
    pool = await get_pool()
    # TODO
    return []
