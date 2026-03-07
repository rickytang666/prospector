import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_TEAM_CONTEXT


def team_context_embed(context):
    repo_url = context["repo_url"]

    embed = discord.Embed(
        title=f"{context['team_name']} — Team Analysis",
        description=f"[{repo_url}]({repo_url})",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    # Extract GitHub owner for thumbnail (e.g. https://github.com/UWOrbital/... -> UWOrbital)
    parts = repo_url.rstrip("/").split("/")
    if len(parts) >= 4 and "github.com" in parts:
        owner = parts[parts.index("github.com") + 1]
        embed.set_thumbnail(url=f"https://github.com/{owner}.png")

    embed.add_field(
        name="Subsystems",
        value="\n".join(f"• {s}" for s in context["subsystems"]),
        inline=False
    )

    embed.add_field(
        name="Blockers",
        value="\n".join(f"• {b}" for b in context["blockers"]),
        inline=False
    )

    embed.add_field(
        name="Tech Stack",
        value=" ".join(f"`{t}`" for t in context["tech_stack"]),
        inline=False
    )

    return embed


class AnalyzeTeam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analyze-team", description="Analyze the configured team repository and infer team context.")
    async def analyze_team(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        config = interaction.client.team_configs.get(guild_id)

        if not config:
            await interaction.response.send_message("Run `/setup-team` first.")
            return

        await interaction.response.defer()

        team_context = {**MOCK_TEAM_CONTEXT, "team_name": config["team_name"], "repo_url": config["repo_url"]}
        interaction.client.team_context_cache[guild_id] = team_context

        embed = team_context_embed(team_context)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))