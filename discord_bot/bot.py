import asyncio
import os
import sys
import discord
from discord.ext import commands

sys.path.insert(0, os.path.dirname(__file__))

from config import TOKEN, GUILD_ID

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

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

asyncio.run(main())