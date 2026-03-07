import discord


def _parse_subject_body(draft: str) -> tuple[str, str]:
    lines = draft.strip().split("\n", 1)
    subject_line = lines[0].strip()
    if subject_line.lower().startswith("subject:"):
        subject = subject_line[len("subject:"):].strip()
    else:
        subject = subject_line
    body = lines[1].strip() if len(lines) > 1 else ""
    return subject, body


def email_draft_embed(draft: str, organization: str, email_type: str) -> discord.Embed:
    subject, body = _parse_subject_body(draft)
    embed = discord.Embed(
        title=f"{email_type.title()} Draft — {organization}",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Subject", value=subject, inline=False)
    preview = body if len(body) <= 1000 else body[:997] + "..."
    embed.add_field(name="Body", value=f"```{preview}```", inline=False)
    embed.set_footer(text="Edit Draft to modify • Copy for raw text")
    return embed


def email_sent_embed(to_email: str, draft: str) -> discord.Embed:
    subject, body = _parse_subject_body(draft)
    embed = discord.Embed(
        title="Email Sent",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="To", value=to_email, inline=True)
    embed.add_field(name="Subject", value=subject, inline=True)
    preview = body if len(body) <= 1000 else body[:997] + "..."
    embed.add_field(name="Body", value=f"```{preview}```", inline=False)
    return embed


def team_context_embed(context):
    repo_url = context["repo_url"]

    embed = discord.Embed(
        title=f"{context['team_name']} — Team Analysis",
        description=f"[{repo_url}]({repo_url})",
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    parts = repo_url.rstrip("/").split("/")
    if len(parts) >= 4 and "github.com" in parts:
        owner = parts[parts.index("github.com") + 1]
        embed.set_thumbnail(url=f"https://github.com/{owner}.png")

    embed.add_field(
        name="Subsystems",
        value="\n".join(f"• {s}" for s in context["subsystems"]),
        inline=False
    )

    embed.add_field(
        name="Blockers",
        value="\n".join(f"• {b}" for b in context["blockers"]),
        inline=False
    )

    embed.add_field(
        name="Tech Stack",
        value=" ".join(f"`{t}`" for t in context["tech_stack"]),
        inline=False
    )

    return embed


def score_bar(score, length=10):
    filled = round(score * length)
    return f"{'█' * filled}{'░' * (length - filled)} {int(score * 100)}%"


def candidates_embed(candidates, query):
    top = candidates[:5]

    embed = discord.Embed(
        title="Top Support Matches",
        description=f'{len(top)} matches for *"{query}"*',
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )

    for i, c in enumerate(top, start=1):
        reasons = "\n".join(f"> {r}" for r in c["matched_reasons"])
        embed.add_field(
            name=f"{i}. {c['name']}",
            value=f"`{score_bar(c['overall_score'])}`\n{reasons}",
            inline=False
        )

    embed.set_footer(text="Click a button below to see why a candidate fits.")
    return embed


def explanation_embed(data, team_name=None):
    embed = discord.Embed(
        title=data["entity_name"],
        description=f"Match analysis for **{team_name}**" if team_name else None,
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow()
    )

    embed.add_field(
        name="Why it helps",
        value="\n".join(f"> {r}" for r in data["why_it_helps"]),
        inline=False
    )

    embed.add_field(
        name="Why they may care",
        value="\n".join(f"> {r}" for r in data["why_they_may_care"]),
        inline=False
    )

    embed.add_field(
        name="Recommended ask",
        value=f"```{data['recommended_ask']}```",
        inline=False
    )

    return embed


def recruit_gap_embed(gaps, team_name):
    embed = discord.Embed(
        title=f"{team_name} — Recruiting Gaps",
        description=f"{len(gaps)} inferred gap{'s' if len(gaps) != 1 else ''} detected",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow()
    )

    for gap in gaps:
        embed.add_field(
            name=gap["role"],
            value=f"> {gap['reason']}",
            inline=False
        )

    return embed
