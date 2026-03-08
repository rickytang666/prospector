import discord
from discord_bot.ui.embeds import explanation_embed


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
        await interaction.response.send_message(
            f"Use `/explain-match {entity_id}` for a full explanation.",
            ephemeral=True
        )


class CandidateSelectView(discord.ui.View):

    def __init__(self, candidates):
        super().__init__(timeout=180)
        self.add_item(CandidateSelect(candidates))
