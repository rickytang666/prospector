import discord
from discord_bot.ui.embeds import explanation_embed
from testing_info import MOCK_EXPLANATIONS


class CandidateSelect(discord.ui.Select):

    def __init__(self, candidates):
        options = [
            discord.SelectOption(
                label=c["name"],
                value=c["entity_id"],
                description=f"Score: {int(c['overall_score'] * 100)}%"
            )
            for c in candidates[:25]
        ]

        super().__init__(
            placeholder="Select a candidate to explain...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        entity_id = self.values[0]
        explanation = MOCK_EXPLANATIONS.get(entity_id)

        if not explanation:
            await interaction.response.send_message(
                f"No explanation available for **{entity_id}**.",
                ephemeral=True
            )
            return

        team_context = interaction.client.team_context_cache.get(interaction.guild_id)
        team_name = team_context["team_name"] if team_context else None
        embed = explanation_embed(explanation, team_name=team_name)
        await interaction.response.send_message(embed=embed)


class CandidateSelectView(discord.ui.View):

    def __init__(self, candidates):
        super().__init__(timeout=180)
        self.add_item(CandidateSelect(candidates))
