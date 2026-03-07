import asyncio
import os
import sys
import pathlib
import discord
from discord.ext import commands

# Ensure both discord_bot/ and project root are importable regardless of how the
# process is started (python discord_bot/bot.py vs uvicorn main:app).
_BOT_DIR = pathlib.Path(__file__).parent
_ROOT_DIR = _BOT_DIR.parent
# Ensure project root is reachable (for storage, retrieval, internal_context).
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
# Unconditionally place discord_bot/ at index 0 — it must shadow the root-level
# config.py so that cog imports like `from config import GEMINI_API_KEY` resolve
# to discord_bot/config.py, not the backend config.
# (When run as `python discord_bot/bot.py` Python pre-populates sys.path[0] with
# the script dir, but inserting ROOT above pushes it back to index 1.)
try:
    sys.path.remove(str(_BOT_DIR))
except ValueError:
    pass
sys.path.insert(0, str(_BOT_DIR))

from config import DISCORD_TOKEN, GUILD_ID

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

bot.team_configs = {}
bot.team_context_cache = {}
bot.email_draft_cache = {}

COGS = [
    "cogs.setup_team",
    "cogs.analyze_team",
    "cogs.find_support",
    "cogs.explain_match",
    "cogs.recruit_gap",
    "cogs.sample_email",
    "cogs.send_email",
]

async def load_cogs():
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {e}")

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    # Copy commands to guild first, then wipe global so there's no duplicate
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    bot.tree.clear_commands(guild=None)
    await bot.tree.sync()
    print(f"Logged in as {bot.user}")

async def start_bot():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


async def main():
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
