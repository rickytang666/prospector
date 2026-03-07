import discord
from ui.embeds import explanation_embed
from testing_info import MOCK_EXPLANATIONS


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
