# /chat: RAG-backed thread; internal context is only for the configured team by name.

import asyncio
import json
import os
import time
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from openai import AsyncOpenAI


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


def _get_context_pack(team_context, query):
    from retrieval.context_pack import retrieve_context_pack
    return retrieve_context_pack(
        team_context=team_context,
        query=query,
        k_entities=5,
        k_chunks=8,
    )


def _format_rag_for_prompt(pack):
    """Turn context_pack into a string block for the model."""
    if not pack:
        return ""
    parts = []
    team = pack.get("team_name", "")
    if team:
        parts.append(f"Team: {team}")
    entities = pack.get("entity_matches", [])[:5]
    if entities:
        parts.append("\nRelevant sponsors/entities (from our database):")
        for e in entities:
            name = e.get("name", "")
            reasons = e.get("matched_reasons") or []
            snippets = e.get("evidence_snippets") or []
            snip = " | ".join(reasons[:2]) if reasons else (snippets[0][:200] if snippets else "")
            parts.append(f"- {name}: {snip}")
    chunks = pack.get("internal_chunks", [])[:5]
    if chunks and team:
        parts.append(f"\nRelevant internal context (only for team \"{team}\" — ingested docs/repo):")
        for c in chunks:
            src = c.get("source", "internal")
            text = (c.get("text") or "")[:280]
            parts.append(f"- [{src}] {text}")
    if not parts:
        return ""
    return "\n".join(parts).strip()


def _build_prompt(history_turns, new_content, rag_block, team_name):
    """Single prompt string: RAG context + conversation history + new message."""
    parts = []
    if rag_block:
        parts.append("Retrieved context (use this to answer):\n" + rag_block)
    parts.append("\nConversation so far:")
    for role, text in history_turns:
        label = "User" if role == "user" else "Assistant"
        parts.append(f"{label}: {text}")
    parts.append(f"\nUser: {new_content}")
    parts.append("\nAssistant:")
    return "\n".join(parts)


def _system_instruction(team_name: str) -> str:
    return f"""You are a helpful assistant for the design team "{team_name}".

You have two kinds of context:
1) Internal context: ONLY ingested docs/repo for "{team_name}" (the team named above). Do NOT claim access to other teams' Notion, GitHub, or Confluence. If you don't have a relevant chunk for something, say you don't have that info for this team.
2) External data: a database of sponsors and support providers (companies, grants, etc.).

Use the retrieved context when relevant. Be concise. Reply in plain text (no markdown code blocks unless showing code)."""


async def _generate_reply(prompt: str, team_name: str):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return "OpenRouter API key not configured."
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    system = _system_instruction(team_name or "the team")
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

    @app_commands.command(name="chat", description="Start a new thread to chat with context from your team and our sponsor database.")
    async def chat(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(self.bot, interaction.guild_id, interaction.user.id)
        if not team_context:
            await interaction.followup.send(
                "Run `/configure-team add` to join a team first. Use `/my-team` to see options. Context loads from the database when you chat.",
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
            description=f"Ask me anything. I have context from **{team_name}** and our sponsor/entity database.",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="How it works",
            value="Type your message in this thread. I'll use conversation history and RAG (internal + external data) to reply. Use `/chat` again in the channel to start a new thread.",
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
        team_context = await get_team_context_for_member(self.bot, guild_id, message.author.id)
        if not team_context:
            await thread.send("Run `/configure-team add` to join a team (use `/my-team` to see options).")
            return
        query = (message.content or "").strip()
        if not query:
            return

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

        rag_block = ""
        if team_context:
            try:
                pack = await asyncio.to_thread(_get_context_pack, team_context, query)
                rag_block = _format_rag_for_prompt(pack)
            except Exception:
                pass

        team_name = (team_context or {}).get("team_name", "the team")
        key = (message.author.id, thread.id)
        now = time.monotonic()
        if key in _chat_last and (now - _chat_last[key]) < CHAT_COOLDOWN_SEC:
            await thread.send("Please wait a few seconds between messages.")
            return
        _chat_last[key] = now

        prompt = _build_prompt(history, query, rag_block, team_name)

        async with thread.typing():
            try:
                reply = await _generate_reply(prompt, team_name)
            except Exception as e:
                reply = f"Sorry, I couldn't generate a reply: {e}"

        if not reply:
            reply = "I didn't get a reply from the model."
        await thread.send(reply[:2000])


async def setup(bot):
    await bot.add_cog(Chat(bot))
