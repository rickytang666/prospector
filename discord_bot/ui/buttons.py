import discord
from discord.ext import commands
from ui.embeds import explanation_embed
from testing_info import MOCK_EXPLANATIONS


class CopyButton(discord.ui.Button):
    def __init__(self, draft: str):
        super().__init__(label="Copy", style=discord.ButtonStyle.secondary)
        self.draft = draft

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.draft, ephemeral=True)


class EditEmailModal(discord.ui.Modal, title="Edit Email Draft"):
    body = discord.ui.TextInput(
        label="Email", style=discord.TextStyle.paragraph, max_length=4000
    )

    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__()
        self.body.default = draft
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        edited = self.body.value
        self.bot.email_draft_cache[interaction.guild_id] = edited

        view = discord.ui.View(timeout=300)
        view.add_item(CopyButton(edited))
        await interaction.response.send_message(
            f"```\n{edited}\n```", view=view, ephemeral=True
        )


class EditEmailButton(discord.ui.Button):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(label="Edit Draft", style=discord.ButtonStyle.secondary)
        self.draft = draft
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditEmailModal(self.draft, self.bot))


class EmailView(discord.ui.View):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(timeout=300)
        self.add_item(EditEmailButton(draft, bot))
        self.add_item(CopyButton(draft))


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
