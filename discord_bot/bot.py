import asyncio
import os
import sys
import pathlib
import traceback
import discord
from discord import app_commands
from discord.ext import commands

_ROOT_DIR = pathlib.Path(__file__).parent.parent.resolve()
# Only the project root needs to be on sys.path.
# Discord-specific cogs use explicit `from discord_bot.config import X` so they
# never clash with the backend root config.py.
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from discord_bot.config import DISCORD_TOKEN, GUILD_ID

if not GUILD_ID:
    raise ValueError("GUILD_ID environment variable is not set — cannot sync slash commands.")

class BotTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from datetime import datetime, timezone
        age = (datetime.now(timezone.utc) - interaction.created_at).total_seconds()
        cmd = interaction.command.name if interaction.command else "?"
        print(f"[interaction] /{cmd} age={age:.2f}s")
        if not getattr(interaction.client, "synced", False):
            try:
                await interaction.response.send_message("Bot is still starting up, please try again in a few seconds.", ephemeral=True)
            except Exception:
                pass
            return False
        return True

intents = discord.Intents.default()
intents.message_content = True  # required for /chat thread messages

bot = commands.Bot(command_prefix="!", intents=intents, tree_cls=BotTree)

bot.team_configs = {}
bot.team_context_cache = {}
bot.email_draft_cache = {}
bot.chat_threads = set()
bot.synced = False

COGS = [
    "discord_bot.cogs.help_cog",
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
            print(f"[cog] Loaded {cog}")
        except Exception as e:
            print(f"[cog] FAILED to load {cog}: {e}")
            traceback.print_exc()

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    if isinstance(error, app_commands.CommandInvokeError) and isinstance(getattr(error, "original", None), discord.NotFound):
        original = error.original
        if getattr(original, "code", None) == 10062:
            print(f"[cmd timeout] /{interaction.command.name if interaction.command else '?'} by {interaction.user}: interaction expired before ack")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("That command timed out before Discord acknowledged it. Please run it again.", ephemeral=True)
                elif interaction.channel:
                    await interaction.channel.send(f"{interaction.user.mention} that command timed out before Discord acknowledged it. Please run it again.")
            except Exception:
                pass
            return

    print(f"[cmd error] /{interaction.command.name if interaction.command else '?'} by {interaction.user}: {error}")
    traceback.print_exc()
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(f"Something went wrong: `{error}`", ephemeral=True)
        else:
            await interaction.followup.send(f"Something went wrong: `{error}`", ephemeral=True)
    except Exception:
        pass

@bot.event
async def on_ready():
    print(f"[on_ready] connected as {bot.user}")
    if bot.synced:
        print(f"[on_ready] reconnected, skipping sync")
        return
    print(f"[on_ready] syncing commands...")
    guild = discord.Object(id=GUILD_ID)
    try:
        bot.tree.copy_global_to(guild=guild)
        await asyncio.wait_for(bot.tree.sync(guild=guild), timeout=20)
        print(f"[on_ready] guild sync complete")
    except asyncio.TimeoutError:
        print("[on_ready] sync timed out after 20s; continuing startup with existing registered commands")
    except Exception as e:
        print(f"[on_ready] sync error: {e}")
        traceback.print_exc()
    bot.synced = True
    print(f"[on_ready] ready")

async def start_bot():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


async def main():
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
