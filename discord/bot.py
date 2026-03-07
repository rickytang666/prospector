import asyncio
import discord
from discord.ext import commands
from config import TOKEN

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

bot.team_configs = {}
bot.team_context_cache = {}

async def load_cogs():
    await bot.load_extension("cogs.setup_team")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

asyncio.run(main())