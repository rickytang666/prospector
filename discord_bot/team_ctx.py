"""Resolve current user's team context from cache or DB (after configure-team + analyze-team)."""
from storage import db


async def get_team_context_for_member(bot, guild_id, user_id):
    key = (str(guild_id), str(user_id))
    cache = getattr(bot, "team_context_cache", None) or {}
    if key in cache:
        return cache[key]
    ctx = await db.get_team_context_for_user(str(guild_id), str(user_id))
    if ctx:
        if not hasattr(bot, "team_context_cache"):
            bot.team_context_cache = {}
        bot.team_context_cache[key] = ctx
    return ctx
