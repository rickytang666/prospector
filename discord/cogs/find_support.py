import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_CANDIDATES, MOCK_EXPLANATIONS
from ui.embeds import candidates_embed, explanation_embed


class CandidateButton(discord.ui.Button):

    def __init__(self, entity_id, label):
        super().__init__(
            label=f"Explain {label}",
            style=discord.ButtonStyle.primary
        )
        self.entity_id = entity_id

    async def callback(self, interaction: discord.Interaction):
        explanation = MOCK_EXPLANATIONS.get(self.entity_id)

        if not explanation:
            await interaction.response.send_message(
                f"No explanation available for **{self.entity_id}**.",
                ephemeral=True
            )
            return

        team_context = interaction.client.team_context_cache.get(interaction.guild_id)
        team_name = team_context["team_name"] if team_context else None
        embed = explanation_embed(explanation, team_name=team_name)
        await interaction.response.send_message(embed=embed)


class CandidateView(discord.ui.View):

    def __init__(self, candidates):
        super().__init__(timeout=180)

        for candidate in candidates[:5]:
            self.add_item(CandidateButton(candidate["entity_id"], candidate["name"]))


class FindSupport(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="find-support", description="Retrieve ranked external support candidates for your team.")
    async def find_support(self, interaction: discord.Interaction, query: str):

        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)

        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return

        await interaction.response.defer()

        embed = candidates_embed(MOCK_CANDIDATES, query)
        view = CandidateView(MOCK_CANDIDATES)

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FindSupport(bot))
