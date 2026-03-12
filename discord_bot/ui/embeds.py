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
    repo_url = context.get("repo_url") or context.get("repo") or ""

    embed = discord.Embed(
        title=f"{context['team_name']} — Team Analysis",
        url=repo_url or None,
        color=discord.Color.blurple(),
        timestamp=discord.utils.utcnow()
    )

    if repo_url:
        parts = repo_url.rstrip("/").split("/")
        if len(parts) >= 4 and "github.com" in parts:
            owner = parts[parts.index("github.com") + 1]
            embed.set_thumbnail(url=f"https://github.com/{owner}.png")

    summary = context.get("context_summary") or ""
    if summary:
        # trim to fit discord field limit
        preview = summary[:1000] + ("..." if len(summary) > 1000 else "")
        embed.add_field(name="What they're working on", value=preview, inline=False)

    if context.get("subsystems"):
        embed.add_field(
            name="Subsystems",
            value="\n".join(f"• {s}" for s in context["subsystems"]),
            inline=False
        )

    if context.get("blockers"):
        blockers = context["blockers"]
        # blockers can be a list of strings or dicts
        lines = []
        for b in blockers:
            if isinstance(b, dict):
                lines.append(f"• {b.get('summary', str(b))}")
            else:
                lines.append(f"• {b}")
        embed.add_field(name="Active Blockers", value="\n".join(lines), inline=False)

    needs = context.get("inferred_support_needs") or context.get("needs") or []
    if needs:
        embed.add_field(
            name="Support Needs",
            value="\n".join(f"• {n}" for n in needs),
            inline=False
        )

    if context.get("tech_stack"):
        embed.add_field(
            name="Tech Stack",
            value=" ".join(f"`{t}`" for t in context["tech_stack"]),
            inline=False
        )

    gaps = context.get("recruiting_gaps") or []
    if gaps:
        lines = [f"**{g['role']}** — {g['reason']}" for g in gaps]
        embed.add_field(
            name="Recruiting Gaps",
            value="\n".join(lines),
            inline=False
        )

    if not embed.fields:
        embed.description = "No team context found. Try running `/setup-team` to ingest your docs."

    return embed


def score_bar(score, length=10):
    filled = round(score * length)
    return f"{'█' * filled}{'░' * (length - filled)} {int(score * 100)}%"


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

def _blurb_line(c):
    ev = c.get("evidence_snippets") or []
    if not ev:
        return None
    t = str(ev[0]).strip()
    if not t:
        return None
    if " (from " in t:
        t = t.split(" (from ", 1)[0].strip()
    if len(t) > 180:
        t = t[:177].rstrip() + "..."
    return t


def candidates_embed(candidates, query, retrieval_metadata=None, title="Top Support Matches", max_items=5, contact_infos=None):
    top = candidates[:max_items]
    meta = retrieval_metadata or {}
    source = meta.get("candidate_source", "unknown")
    db_status = meta.get("db_status", "n/a")
    contacts = {c["name"]: c for c in (contact_infos or [])}

    embed = discord.Embed(
        title=title,
        description=f'{len(top)} matches for *"{query}"*\nRanked by: `semantic relevance`\nSource: `{source}` • DB: `{db_status}`',
        color=discord.Color.from_rgb(46, 134, 222),
        timestamp=discord.utils.utcnow()
    )

    for i, c in enumerate(top, start=1):
        score = float(c.get("overall_score", 0.0))
        blurb = _blurb_line(c)
        contact = contacts.get(c["name"], {})
        contact_line = ""
        if contact.get("contact_person") or contact.get("contact_email") or contact.get("website"):
            bits = []
            if contact.get("contact_person"):
                bits.append(f"Contact: {contact['contact_person']}")
            if contact.get("contact_email"):
                email = contact["contact_email"]
                verified = contact.get("contact_email_verified", False)
                bits.append(email if verified else f"{email} *(suggested)*")
            if contact.get("website"):
                bits.append(f"[website]({contact['website']})")
            contact_line = " • ".join(bits)
        if not contact_line:
            contact_line = _extract_contact_line(c) or ""
        lines = [
            f"`{score_bar(score)}`",
            f"_{blurb}_" if blurb else "_No summary available._",
        ]
        if contact_line:
            lines.append(contact_line)
        embed.add_field(name=f"{i}. {c['name']}", value="\n".join(lines), inline=False)

    embed.set_footer(text="Explain buttons show evidence and suggested ask.")
    return embed


def explanation_embed(data, team_name=None):
    embed = discord.Embed(
        title=data["entity_name"],
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )

    reason = (data.get("reason") or "").strip()
    if reason:
        embed.add_field(name="Why", value=reason, inline=False)

    # waterloo affinity — most persuasive thing to show
    aff_ev = data.get("waterloo_affinity_evidence") or []
    aff_texts = []
    for ev in aff_ev[:3]:
        if isinstance(ev, dict):
            text = ev.get("text", "")
        else:
            text = getattr(ev, "text", "")
        if text:
            aff_texts.append(f"• {text}")
    if aff_texts:
        embed.add_field(name="Waterloo Connection", value="\n".join(aff_texts), inline=False)

    # contact info
    contact_bits = []
    if data.get("contact_person"):
        contact_bits.append(f"Contact: {data['contact_person']}")
    if data.get("contact_email"):
        email = data["contact_email"]
        verified = data.get("contact_email_verified", False)
        contact_bits.append(email if verified else f"{email} *(suggested)*")
    if data.get("website"):
        contact_bits.append(f"[website]({data['website']})")
    if contact_bits:
        embed.add_field(name="Contact", value=" • ".join(contact_bits), inline=False)

    # score breakdown
    sb = data.get("score_breakdown") or {}
    overall = data.get("overall_score")
    if sb or overall is not None:
        def _bar(v): return score_bar(float(v), length=8)
        lines = []
        if overall is not None:
            lines.append(f"Overall  `{_bar(overall)}`")
        if sb.get("semantic_score") is not None:
            lines.append(f"Semantic `{_bar(sb['semantic_score'])}`")
        if sb.get("support_fit_score") is not None:
            lines.append(f"Support  `{_bar(sb['support_fit_score'])}`")
        if sb.get("waterloo_affinity_score") is not None:
            lines.append(f"Waterloo `{_bar(sb['waterloo_affinity_score'])}`")
        if lines:
            embed.add_field(name="Score Breakdown", value="\n".join(lines), inline=False)

    tags = [t for t in (data.get("tags") or []) if t]
    if tags:
        embed.add_field(name="Tags", value=" ".join(f"`{t}`" for t in tags[:12]), inline=False)

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
