import asyncio
import os
import sys
import pathlib
import discord
from discord.ext import commands

_BOT_DIR = pathlib.Path(__file__).parent.resolve()
_ROOT_DIR = _BOT_DIR.parent
# Project root must be in sys.path for storage/retrieval/internal_context imports.
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))
# discord_bot/ must be at index 0 so discord_bot/config.py (with GEMINI_API_KEY etc.)
# shadows the root config.py. Unconditional remove+insert handles the case where
# Python pre-populated sys.path[0] with the script dir before our code runs.
try:
    sys.path.remove(str(_BOT_DIR))
except ValueError:
    pass
sys.path.insert(0, str(_BOT_DIR))

from config import DISCORD_TOKEN, GUILD_ID

intents = discord.Intents.default()
intents.message_content = True  # required for /chat thread messages

bot = commands.Bot(command_prefix="!", intents=intents)

bot.team_configs = {}
bot.team_context_cache = {}
bot.email_draft_cache = {}
bot.chat_threads = set()

COGS = [
    "discord_bot.cogs.setup_team",
    "discord_bot.cogs.configure_team",
    "discord_bot.cogs.analyze_team",
    "discord_bot.cogs.add_context",
    "discord_bot.cogs.find_support",
    "discord_bot.cogs.explain_match",
    "discord_bot.cogs.recruit_gap",
    "discord_bot.cogs.chat",
    "discord_bot.cogs.nuke",
    "discord_bot.cogs.remove_from_memory",
    "discord_bot.cogs.sample_email",
    "discord_bot.cogs.send_email",
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
