import discord
from discord.ext import commands
from discord import app_commands
from storage import db
from discord_bot.ui.embeds import recruit_gap_embed


class RecruitGap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recruit-gap", description="Show inferred recruiting needs for your team.")
    async def recruit_gap(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(interaction.client, guild_id, user_id)

        if not team_context:
            await interaction.followup.send("Run `/configure-team add` first (use `/my-team` to see teams).", ephemeral=True)
            return

        gaps = team_context.get("recruiting_gaps", [])
        if not gaps:
            gaps = [{"role": need, "reason": "Inferred from analyzed team context."} for need in team_context.get("inferred_support_needs", [])]

        if not gaps:
            await interaction.followup.send("No recruiting gaps inferred for this team.")
            return

        embed = recruit_gap_embed(gaps, team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RecruitGap(bot))
