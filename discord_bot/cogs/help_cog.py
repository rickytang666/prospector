"""Slash command /help — list commands and what they do."""
import discord
from discord import app_commands
from discord.ext import commands

HELP_SECTIONS = [
    ("Getting started", [
        ("/configure-team", "Add or remove yourself from a team (saved to your profile)."),
        ("/my-team", "See teams you're in, which is active, and teams you can join."),
        ("/set-active-team", "Switch which team is used for /chat, /find-support, etc."),
        ("/analyze-team", "Load and view your team's summary (tech stack, blockers, recruiting gaps)."),
    ]),
    ("Admin / setup", [
        ("/setup-team", "Register a team and ingest its repo (first step, server-wide)."),
    ]),
    ("Context & memory", [
        ("/add-context", "Add a doc source (Notion, Confluence, or URL) to your team."),
        ("/remove_from_memory", "Find and delete chunks by search query (e.g. fix wrong info)."),
        ("/nuke", "Wipe all data for your team (confirm with ✅)."),
    ]),
    ("Find support & explain", [
        ("/find-support", "Get ranked support candidates for a query."),
        ("/find-providers", "Find providers for a technical need."),
        ("/explain-match", "Explain why a candidate fits your team."),
        ("/recruit-gap", "Show inferred recruiting needs for your team."),
    ]),
    ("Chat & email", [
        ("/chat", "Start a thread to chat with RAG (your team context + sponsor DB)."),
        ("/sample_email", "Generate an email draft using AI."),
        ("/send_email", "Send the latest email draft via Gmail."),
    ]),
]


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="List bot commands and what they do.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Command reference",
            description="Use these slash commands. Start with `/configure-team add` and `/my-team`.",
            color=discord.Color.blue(),
        )
        for section_name, items in HELP_SECTIONS:
            lines = [f"**{name}** — {desc}" for name, desc in items]
            embed.add_field(name=section_name, value="\n".join(lines), inline=False)
        embed.set_footer(text="Context loads from the database; use /analyze-team to view the summary.")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
