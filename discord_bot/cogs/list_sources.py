import discord
from discord.ext import commands
from discord import app_commands
from storage import db


class ListSources(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="list-sources", description="Show all ingested sources for your team.")
    async def list_sources(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        await interaction.response.defer(ephemeral=True)

        team_name = await db.get_user_team(guild_id, user_id)
        if not team_name:
            await interaction.followup.send("Run `/configure-team add` first.", ephemeral=True)
            return

        rows = await db.get_chunks(team_name)
        if not rows:
            await interaction.followup.send(f"No sources ingested for **{team_name}** yet.", ephemeral=True)
            return

        # group by source_url, track source_type and chunk count
        sources: dict[str, dict] = {}
        for r in rows:
            url = r.get("source_url") or "(no url)"
            stype = r.get("source_type") or "unknown"
            if url not in sources:
                sources[url] = {"type": stype, "count": 0}
            sources[url]["count"] += 1

        embed = discord.Embed(
            title=f"{team_name} — Ingested Sources",
            description=f"{len(sources)} source(s), {len(rows)} total chunks",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        # group by type for cleaner display
        by_type: dict[str, list[tuple[str, int]]] = {}
        for url, info in sources.items():
            t = info["type"]
            by_type.setdefault(t, []).append((url, info["count"]))

        type_labels = {
            "github_readme": "GitHub READMEs",
            "github_issue": "GitHub Issues",
            "notion": "Notion",
            "confluence": "Confluence",
            "website": "Website / URL",
        }

        for stype, entries in sorted(by_type.items()):
            label = type_labels.get(stype, stype)
            total_chunks = sum(c for _, c in entries)
            lines = []
            for url, count in entries[:10]:  # cap at 10 per type to avoid hitting embed limit
                short = url if len(url) <= 60 else url[:57] + "..."
                lines.append(f"• [{short}]({url}) — {count} chunk{'s' if count != 1 else ''}")
            if len(entries) > 10:
                lines.append(f"_...and {len(entries) - 10} more_")
            embed.add_field(
                name=f"{label} ({total_chunks} chunks)",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text="Use /add-context to add more • /remove_from_memory to delete specific chunks")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ListSources(bot))
