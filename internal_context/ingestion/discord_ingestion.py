import discord
from internal_context.models import Chunk


def _is_signal(msg: discord.Message) -> bool:
    # always keep messages with code blocks or links
    has_code = "```" in msg.content
    has_link = "http://" in msg.content or "https://" in msg.content
    has_attachment = len(msg.attachments) > 0
    if has_code or has_link or has_attachment:
        return True
    # filter out short chitchat
    return len(msg.content) >= 100


def _group_into_chunks(messages: list[discord.Message], team_name: str, target_words: int = 300) -> list[Chunk]:
    chunks = []
    current = []
    current_words = 0
    first_msg = None

    for msg in messages:
        line = f"{msg.author.display_name}: {msg.content}"
        words = len(line.split())

        if first_msg is None:
            first_msg = msg

        current.append(line)
        current_words += words

        if current_words >= target_words:
            chunks.append(Chunk(
                team_name=team_name,
                source_type="discord",
                source_url=first_msg.jump_url,
                content="\n".join(current),
            ))
            current = []
            current_words = 0
            first_msg = None

    if current and first_msg:
        chunks.append(Chunk(
            team_name=team_name,
            source_type="discord",
            source_url=first_msg.jump_url,
            content="\n".join(current),
        ))

    return chunks
