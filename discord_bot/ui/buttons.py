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


class SendEmailModal(discord.ui.Modal, title="Send Email"):
    to_email = discord.ui.TextInput(
        label="Recipient email address",
        placeholder="sponsorship@company.com",
        max_length=200,
    )

    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__()
        self.draft = draft
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        from discord_bot.mailer import send_email as _send_email
        from discord_bot.ui.embeds import email_sent_embed, _parse_subject_body
        await interaction.response.defer(ephemeral=True)
        subject, body = _parse_subject_body(self.draft)
        try:
            await _send_email(str(self.to_email), subject, body)
        except Exception as e:
            await interaction.followup.send(f"Failed to send: {e}", ephemeral=True)
            return
        embed = email_sent_embed(str(self.to_email), self.draft)
        await interaction.followup.send(embed=embed, ephemeral=True)


class SendEmailButton(discord.ui.Button):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(label="Send", style=discord.ButtonStyle.success)
        self.draft = draft
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SendEmailModal(self.draft, self.bot))


class EmailView(discord.ui.View):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(timeout=300)
        self.add_item(EditEmailButton(draft, bot))
        self.add_item(CopyButton(draft))
        self.add_item(SendEmailButton(draft, bot))


class CandidateButton(discord.ui.Button):

    def __init__(self, candidate):
        name = candidate.get("name", "Candidate")
        super().__init__(
            label=f"Explain {name[:20]}",
            style=discord.ButtonStyle.primary,
        )
        self.candidate = candidate

    async def callback(self, interaction: discord.Interaction):
        c = self.candidate
        reasons = c.get("matched_reasons") or []
        explanation = {
            "entity_name": c.get("name", c.get("entity_id", "Candidate")),
            "reason": reasons[0] if reasons else "",
            "tags": c.get("tags") or [],
            "contact_person": "",
            "contact_email": "",
            "contact_email_verified": False,
            "website": c.get("canonical_url", ""),
            "waterloo_affinity_evidence": c.get("waterloo_affinity_evidence") or [],
            "overall_score": c.get("overall_score", 0.0),
            "score_breakdown": c.get("score_breakdown") or {},
        }
        key = (str(interaction.guild_id), str(interaction.user.id))
        team_context = getattr(interaction.client, "team_context_cache", {}).get(key)
        team_name = team_context["team_name"] if team_context else None
        embed = explanation_embed(explanation, team_name=team_name)
        await interaction.response.send_message(embed=embed)


class DraftEmailButton(discord.ui.Button):

    def __init__(self, candidate):
        name = candidate.get("name", "Candidate")
        super().__init__(
            label=f"Draft Email → {name[:18]}",
            style=discord.ButtonStyle.success,
        )
        self.candidate = candidate

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from discord_bot.ai import generate_email
        from discord_bot.ui.embeds import email_draft_embed

        key = (str(interaction.guild_id), str(interaction.user.id))
        team_context = getattr(interaction.client, "team_context_cache", {}).get(key)
        if not team_context:
            await interaction.followup.send("Run `/analyze-team` first to load your team context.", ephemeral=True)
            return

        c = self.candidate
        org = c.get("name", "this company")
        reasons = c.get("matched_reasons") or []
        matched_reason = reasons[0] if reasons else ""

        try:
            draft = await generate_email(team_context, org, "sponsorship", matched_reason)
        except Exception as e:
            await interaction.followup.send(f"Failed to generate email: {e}", ephemeral=True)
            return

        interaction.client.email_draft_cache[interaction.guild_id] = draft
        embed = email_draft_embed(draft, org, "sponsorship")
        view = EmailView(draft, interaction.client)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class CandidateView(discord.ui.View):

    def __init__(self, candidates):
        super().__init__(timeout=300)

        for candidate in candidates[:7]:
            self.add_item(CandidateButton(candidate))
        for candidate in candidates[:7]:
            self.add_item(DraftEmailButton(candidate))
