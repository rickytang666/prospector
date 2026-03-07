import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_CANDIDATES, MOCK_EXPLANATIONS


def candidates_embed(candidates, query):
    embed = discord.Embed(
        title="Top Support Matches",
        description=f'Query: *"{query}"*',
        color=discord.Color.blue()
    )

    for i, c in enumerate(candidates[:5], start=1):
        embed.add_field(
            name=f"{i}. {c['name']} — score {c['overall_score']:.2f}",
            value="\n".join(f"• {r}" for r in c["matched_reasons"]),
            inline=False
        )

    embed.set_footer(text="Click a button below to see why a candidate fits.")
    return embed


def explanation_embed(data):
    embed = discord.Embed(
        title=data["entity_name"],
        color=discord.Color.green()
    )

    embed.add_field(
        name="Why it helps",
        value="\n".join(f"• {r}" for r in data["why_it_helps"]),
        inline=False
    )

    embed.add_field(
        name="Why they may care",
        value="\n".join(f"• {r}" for r in data["why_they_may_care"]),
        inline=False
    )

    embed.add_field(
        name="Recommended ask",
        value=data["recommended_ask"],
        inline=False
    )

    return embed


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

        embed = explanation_embed(explanation)
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
