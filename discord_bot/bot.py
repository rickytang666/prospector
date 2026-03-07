import discord
from discord.ext import commands
from config import DISCORD_TOKEN, GUILD_ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

bot.team_configs = {}
bot.team_context_cache = {}


async def load_cogs():
    await bot.load_extension("discord_bot.cogs.setup_team")
    # await bot.load_extension("discord_bot.cogs.analyze_team")
    # await bot.load_extension("discord_bot.cogs.find_support")
    # await bot.load_extension("discord_bot.cogs.explain_match")
    # await bot.load_extension("discord_bot.cogs.recruit_gap")


@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    print(f"logged in as {bot.user}")


async def start_bot():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)
