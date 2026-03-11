import re
import discord
from discord.ext import commands
from discord import app_commands
from storage import db


def _group_key(source_type: str, url: str) -> str:
    """collapse individual page urls into a meaningful group label"""
    if not url or url == "(no url)":
        return "(unknown)"
    if source_type in ("github_readme", "github_issue"):
        # extract org/repo from github url
        m = re.search(r"github\.com/([^/]+/[^/]+)", url)
        return f"github.com/{m.group(1)}" if m else url
    if source_type == "confluence":
        # extract space key: /wiki/spaces/KEY
        m = re.search(r"/wiki/spaces/([^/]+)", url)
        return m.group(1) + " space" if m else url
    if source_type in ("notion", "website"):
        # group by domain
        m = re.search(r"https?://([^/]+)", url)
        return m.group(1) if m else url
    return url


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

        # group by (source_type, group_key) → chunk count + one representative url
        groups: dict[tuple[str, str], dict] = {}
        for r in rows:
            url = r.get("source_url") or "(no url)"
            stype = r.get("source_type") or "unknown"
            key = (stype, _group_key(stype, url))
            if key not in groups:
                groups[key] = {"count": 0, "url": url}
            groups[key]["count"] += 1

        # group by source_type
        by_type: dict[str, list[tuple[str, int, str]]] = {}
        for (stype, label), info in sorted(groups.items()):
            by_type.setdefault(stype, []).append((label, info["count"], info["url"]))

        type_labels = {
            "github_readme": "GitHub READMEs",
            "github_issue": "GitHub Issues",
            "notion": "Notion",
            "confluence": "Confluence",
            "website": "Website / URL",
        }

        total_chunks = len(rows)
        total_sources = len(groups)
        embed = discord.Embed(
            title=f"{team_name} — Ingested Sources",
            description=f"{total_sources} source(s), {total_chunks} total chunks",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        for stype, entries in sorted(by_type.items()):
            label = type_labels.get(stype, stype)
            type_chunks = sum(c for _, c, _ in entries)
            lines = []
            for group_label, count, url in sorted(entries, key=lambda x: -x[1]):
                line = f"• [{group_label}]({url}) — {count} chunk{'s' if count != 1 else ''}"
                if len("\n".join(lines + [line])) > 950:
                    lines.append(f"_...and {len(entries) - len(lines)} more_")
                    break
                lines.append(line)
            embed.add_field(
                name=f"{label} — {type_chunks} chunks",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text="Use /add-context to add more • /remove_from_memory to delete specific chunks")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ListSources(bot))
