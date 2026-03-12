# /chat: pure RAG over team's ingested chunks

import asyncio
import json
import os
import time
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI

from retrieval.models import TeamContext, Blocker


CHAT_COOLDOWN_SEC = 8
_chat_last: dict[tuple[int, int], float] = {}

_THREADS_FILE = Path(__file__).parent.parent.parent / "data" / "chat_threads.json"


def _load_thread_ids() -> set[int]:
    try:
        return set(json.loads(_THREADS_FILE.read_text()))
    except Exception:
        return set()


def _save_thread_ids(ids: set[int]) -> None:
    try:
        _THREADS_FILE.parent.mkdir(exist_ok=True)
        _THREADS_FILE.write_text(json.dumps(list(ids)))
    except Exception as e:
        print(f"failed to save chat_threads: {e}")


def _dict_to_team_context(d: dict) -> TeamContext:
    ab = []
    for b in (d.get("active_blockers") or []):
        if isinstance(b, Blocker):
            ab.append(b)
        elif isinstance(b, dict):
            ab.append(Blocker(
                summary=str(b.get("summary", "")),
                tags=[str(x) for x in (b.get("tags") or [])],
                severity=str(b.get("severity", "medium")),
            ))
    return TeamContext(
        team_name=str(d.get("team_name", "unknown")),
        repo=str(d.get("repo", "")),
        active_blockers=ab,
        subsystems=[str(x) for x in (d.get("subsystems") or [])],
        inferred_support_needs=[str(x) for x in (d.get("inferred_support_needs") or [])],
        context_summary=str(d.get("context_summary", "")),
    )


def _fetch_chunks(team_context: TeamContext, query: str) -> list[dict]:
    from retrieval.internal_retrieval import fetch_internal_chunks_with_meta
    result = fetch_internal_chunks_with_meta(team_context=team_context, query=query, k=15)
    return result.get("chunks") or []


def _format_chunks(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for c in chunks[:12]:
        text = (c.get("text") or "")[:400]
        parts.append(f"---\n{text}")
    return "\n".join(parts)


async def _generate_reply(chunks_block: str, history_turns: list, new_content: str, team_name: str) -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return "OpenRouter API key not configured."
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)

    system = f"""You are a knowledgeable assistant for the engineering design team "{team_name}".
You have access to the team's actual documents — GitHub issues, READMEs, Confluence pages, and meeting notes.
Answer directly and specifically. Synthesize information across the docs to give a real answer.
Don't list bullet points of random facts — respond like you actually understand the team's situation.
Only fall back to "I don't have that info" if the context genuinely has nothing relevant."""

    # build the user message: context + history + query
    parts = []
    if chunks_block:
        parts.append(f"Context from {team_name}'s docs:\n{chunks_block}")
    if history_turns:
        parts.append("\nConversation so far:")
        for role, text in history_turns:
            label = "User" if role == "user" else "Assistant"
            parts.append(f"{label}: {text}")
    parts.append(f"\nUser: {new_content}")
    parts.append("\nAssistant:")

    prompt = "\n".join(parts)

    resp = await client.chat.completions.create(
        model="google/gemini-2.5-flash-lite",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
    )
    return (resp.choices[0].message.content or "").strip()


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, "chat_threads"):
            bot.chat_threads = _load_thread_ids()

    @app_commands.command(name="chat", description="Start a new thread to chat with context from your team's ingested docs.")
    async def chat(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(self.bot, interaction.guild_id, interaction.user.id)
        if not team_context:
            await interaction.followup.send(
                "Run `/configure-team add` to join a team first. Use `/my-team` to see options.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                "Run `/chat` in a text channel (not inside a thread).",
                ephemeral=True,
            )
            return

        try:
            thread = await channel.create_thread(
                name=f"chat-{interaction.user.display_name[:20]}",
                type=discord.ChannelType.public_thread,
            )
        except Exception as e:
            await interaction.followup.send(f"Could not create thread: {e}", ephemeral=True)
            return

        self.bot.chat_threads.add(thread.id)
        _save_thread_ids(self.bot.chat_threads)
        team_name = team_context.get("team_name", "your team")

        embed = discord.Embed(
            title="Chat",
            description=f"Ask me anything about **{team_name}**. I'll search your team's ingested docs to answer.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="How it works",
            value="Type your message in this thread. I'll pull relevant chunks from your team's GitHub/Confluence/Notion docs and answer based on those.",
            inline=False,
        )
        await thread.send(embed=embed)
        await interaction.followup.send(f"Go to {thread.mention} to chat.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.channel.id not in getattr(self.bot, "chat_threads", set()):
            return

        thread = message.channel
        guild_id = message.guild.id
        from discord_bot.team_ctx import get_team_context_for_member
        team_context_dict = await get_team_context_for_member(self.bot, guild_id, message.author.id)
        if not team_context_dict:
            await thread.send("Run `/configure-team add` to join a team (use `/my-team` to see options).")
            return

        query = (message.content or "").strip()
        if not query:
            return

        # cooldown check
        ck = (message.author.id, thread.id)
        now = time.monotonic()
        if ck in _chat_last and (now - _chat_last[ck]) < CHAT_COOLDOWN_SEC:
            await thread.send("Please wait a few seconds between messages.")
            return
        _chat_last[ck] = now

        # grab recent history
        history = []
        try:
            async for m in thread.history(limit=12, before=message):
                if m.author.bot:
                    history.append(("model", m.content or ""))
                else:
                    history.append(("user", m.content or ""))
        except Exception:
            pass
        history.reverse()
        history = history[-10:]

        team_ctx = _dict_to_team_context(team_context_dict)
        team_name = team_ctx.team_name

        chunks_block = ""
        try:
            chunks = await asyncio.to_thread(_fetch_chunks, team_ctx, query)
            chunks_block = _format_chunks(chunks)
        except Exception as e:
            print(f"[chat] chunk fetch failed: {e}")

        async with thread.typing():
            try:
                reply = await _generate_reply(chunks_block, history, query, team_name)
            except Exception as e:
                reply = f"Sorry, couldn't generate a reply: {e}"

        if not reply:
            reply = "I didn't get a reply from the model."
        await thread.send(reply[:2000])


async def setup(bot):
    await bot.add_cog(Chat(bot))
