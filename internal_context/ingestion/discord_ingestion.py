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

async def fetch_channel_chunks(
    client: discord.Client,
    channel_id: int,
    team_name: str,
    limit: int = 500,
) -> list[Chunk]:
    channel = client.get_channel(channel_id)
    if channel is None:
        print(f"channel {channel_id} not found (bot might not be in that server)")
        return []

    if not isinstance(channel, discord.TextChannel):
        print(f"channel {channel_id} is not a text channel, skipping")
        return []

    print(f"fetching messages from #{channel.name}")

    messages = []
    async for msg in channel.history(limit=limit, oldest_first=True):
        # skip bots and system messages
        if msg.author.bot or msg.type != discord.MessageType.default:
            continue
        if not msg.content.strip():
            continue
        if not _is_signal(msg):
            continue
        messages.append(msg)

    print(f"got {len(messages)} signal messages from #{channel.name}")

    # also pull threads
    thread_messages = []
    for thread in channel.threads:
        async for msg in thread.history(limit=200, oldest_first=True):
            if msg.author.bot or msg.type != discord.MessageType.default:
                continue
            if not msg.content.strip():
                continue
            if not _is_signal(msg):
                continue
            thread_messages.append(msg)

    if thread_messages:
        print(f"got {len(thread_messages)} signal messages from {len(channel.threads)} threads in #{channel.name}")
        messages.extend(thread_messages)

    return _group_into_chunks(messages, team_name)
