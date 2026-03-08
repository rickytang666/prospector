import discord
from discord.ext import commands
from discord_bot.ui.embeds import explanation_embed


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

    def __init__(self, candidate):
        super().__init__(
            label=f"Explain {candidate.get('name','Candidate')}",
            style=discord.ButtonStyle.primary
        )
        self.candidate = candidate

    async def callback(self, interaction: discord.Interaction):
        c = self.candidate
        support_types = c.get("support_types") or []
        explanation = {
            "entity_name": c.get("name", c.get("entity_id", "Candidate")),
            "why_it_helps": c.get("matched_reasons") or ["No reasons available."],
            "why_they_may_care": c.get("evidence_snippets") or ["No evidence available."],
            "recommended_ask": support_types[0] if support_types else "Reach out to explore collaboration.",
        }
        team_context = interaction.client.team_context_cache.get(interaction.guild_id)
        team_name = team_context["team_name"] if team_context else None
        embed = explanation_embed(explanation, team_name=team_name)
        await interaction.response.send_message(embed=embed)


class CandidateView(discord.ui.View):

    def __init__(self, candidates):
        super().__init__(timeout=180)

        for candidate in candidates[:5]:
            self.add_item(CandidateButton(candidate))
