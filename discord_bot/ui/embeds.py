import discord
import re


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
        url=repo_url,
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


def _score_breakdown_line(c):
    sb = c.get("score_breakdown") or {}
    sem = float(sb.get("semantic_score", 0.0))
    tag = float(sb.get("tag_overlap_score", 0.0))
    sup = float(sb.get("support_fit_score", 0.0))
    uw = float(sb.get("waterloo_affinity_score", 0.0))
    return f"sem {sem:.2f} • tag {tag:.2f} • support {sup:.2f} • uw {uw:.2f}"

def _uw_tier_from_candidate(c):
    ev = c.get("waterloo_affinity_evidence") or []
    tier = {
        "team_sponsor": (1.00, "Sponsor"),
        "waterloo_partner": (0.90, "Partner"),
        "official_partner": (0.90, "Partner"),
        "waterloo_alumni_founder": (0.75, "Alumni"),
        "alumni_link": (0.75, "Alumni"),
        "startup_incubator": (0.55, "Incubator"),
        "yc_company": (0.35, "YC"),
        "official_page": (0.35, "UW-Linked"),
    }
    best_s = 0.0
    best_l = "None"
    seen = set()
    note = ""
    for x in ev:
        if not isinstance(x, dict):
            continue
        t = str(x.get("type", "")).strip().lower()
        if not t:
            continue
        seen.add(t)
        s, l = tier.get(t, (0.20, "UW-Linked"))
        if s > best_s:
            best_s = s
            best_l = l
            note = str(x.get("text", "")).strip()
    if len(seen) > 1:
        best_s = min(1.0, best_s + 0.05)
    return best_l, best_s, note


def _extract_contact_line(c):
    ev = c.get("evidence_snippets") or []
    txt = " | ".join(str(x) for x in ev if x)
    mail = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", txt)
    url = re.search(r"https?://[^\s)]+", txt)
    if mail and url:
        return f"Contact: {mail.group(0)} • [Link]({url.group(0)})"
    if mail:
        return f"Contact: {mail.group(0)}"
    if url:
        return f"Link: {url.group(0)}"
    return None


def candidates_embed(candidates, query, retrieval_metadata=None, title="Top Support Matches", max_items=5, contact_infos=None):
    top = candidates[:max_items]
    meta = retrieval_metadata or {}
    source = meta.get("candidate_source", "unknown")
    db_status = meta.get("db_status", "n/a")
    contacts = {c["name"]: c for c in (contact_infos or [])}

    embed = discord.Embed(
        title=title,
        description=f'{len(top)} matches for *"{query}"*\nRanked by: `semantic relevance + UW affinity`\nSource: `{source}` • DB: `{db_status}`',
        color=discord.Color.from_rgb(46, 134, 222),
        timestamp=discord.utils.utcnow()
    )

    for i, c in enumerate(top, start=1):
        sb = c.get("score_breakdown") or {}
        sem = float(sb.get("semantic_score", 0.0))
        uw = float(sb.get("waterloo_affinity_score", 0.0))
        tier, tier_score, tier_note = _uw_tier_from_candidate(c)
        reasons = c.get("matched_reasons") or []
        rtxt = "\n".join(f"• {r}" for r in reasons[:2]) if reasons else "• Moderate semantic fit."
        contact = contacts.get(c["name"], {})
        contact_line = ""
        if contact.get("contact_person") or contact.get("contact_email") or contact.get("website"):
            bits = []
            if contact.get("contact_person"):
                bits.append(f"Contact: {contact['contact_person']}")
            if contact.get("contact_email"):
                bits.append(contact["contact_email"])
            if contact.get("website"):
                bits.append(contact["website"])
            contact_line = " • ".join(bits)
        if not contact_line:
            contact_line = _extract_contact_line(c) or ""
        lines = [
            f"`{score_bar(c['overall_score'])}`",
            f"`sem {sem:.2f} • uw {uw:.2f}`",
            f"`UW Tier: {tier} ({tier_score:.2f})`",
            rtxt,
        ]
        if tier_note:
            lines.append(f"_UW evidence: {tier_note}_")
        if contact_line:
            lines.append(contact_line)
        embed.add_field(name=f"{i}. {c['name']}", value="\n".join(lines), inline=False)

    embed.set_footer(text="Explain buttons show evidence and suggested ask.")
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

    ask = data["recommended_ask"]
    ask_preview = ask if len(ask) <= 900 else ask[:897] + "..."
    embed.add_field(
        name="Recommended ask",
        value=f"```{ask_preview}```",
        inline=False
    )

    contact_person = data.get("contact_person", "")
    contact_email = data.get("contact_email", "")
    website = data.get("website", "")
    if contact_person or contact_email or website:
        lines = []
        if contact_person:
            lines.append(f"Contact: {contact_person}")
        if contact_email:
            lines.append(f"Email: {contact_email}")
        if website:
            lines.append(f"Website: {website}")
        embed.add_field(name="How to reach them", value="\n".join(lines), inline=False)

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
