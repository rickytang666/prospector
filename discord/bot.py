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

async def load_cogs():
    await bot.load_extension("cogs.setup_team")
    await bot.load_extension("cogs.analyze_team")
    await bot.load_extension("cogs.find_support")
    await bot.load_extension("cogs.explain_match")
    await bot.load_extension("cogs.recruit_gap")

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

asyncio.run(main())