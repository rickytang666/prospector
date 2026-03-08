#/chat - start a thread for RAG convo 

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from google import genai

from discord_bot.config import GEMINI_API_KEY

# Lazy imports for retrieval (run in thread to avoid blocking)
def _get_context_pack(team_context, query):
    from retrieval.context_pack import retrieve_context_pack
    return retrieve_context_pack(
        team_context=team_context,
        query=query,
        k_entities=5,
        k_chunks=5,
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
    if chunks:
        parts.append("\nRelevant internal context (team docs/repo):")
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


SYSTEM_INSTRUCTION = """You are a helpful assistant for a university design team. You have access to:
1) Internal context: their repo, docs, and team notes.
2) External data: a database of sponsors, companies, and support providers.

Use the retrieved context when relevant to answer accurately. You can also chat generally—be concise and helpful. Reply in plain text (no markdown code blocks unless showing code)."""


async def _generate_reply(prompt):
    if not GEMINI_API_KEY:
        return "Gemini API key not configured."
    client = genai.Client(api_key=GEMINI_API_KEY)

    def _run():
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"system_instruction": SYSTEM_INSTRUCTION},
        )
        return resp.text if hasattr(resp, "text") else str(resp)

    return await asyncio.to_thread(_run)


class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(bot, "chat_threads"):
            bot.chat_threads = set()

    @app_commands.command(name="chat", description="Start a new thread to chat with context from your team and our sponsor database.")
    async def chat(self, interaction: discord.Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        team_context = self.bot.team_context_cache.get(interaction.guild_id)
        if not team_context:
            await interaction.response.send_message(
                "Run `/setup-team` and `/analyze-team` first so I can use your team context and sponsor data.",
                ephemeral=True,
            )
            return

        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Run `/chat` in a text channel (not inside a thread).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            thread = await channel.create_thread(
                name=f"chat-{interaction.user.display_name[:20]}",
                type=discord.ChannelType.public_thread,
            )
        except Exception as e:
            await interaction.followup.send(f"Could not create thread: {e}", ephemeral=True)
            return

        self.bot.chat_threads.add(thread.id)
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
        team_context = self.bot.team_context_cache.get(guild_id)
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
        prompt = _build_prompt(history, query, rag_block, team_name)

        async with thread.typing():
            try:
                reply = await _generate_reply(prompt)
            except Exception as e:
                reply = f"Sorry, I couldn't generate a reply: {e}"

        if not reply:
            reply = "I didn't get a reply from the model."
        await thread.send(reply[:2000])


async def setup(bot):
    await bot.add_cog(Chat(bot))
