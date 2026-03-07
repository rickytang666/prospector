from internal_context.models import Chunk


def chunk_text(text: str, team_name: str, source_type: str, source_url: str, target_words: int = 400) -> list[Chunk]:
    """split text into chunks of ~target_words words, splitting on paragraph breaks"""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    current = []
    current_words = 0

    for para in paragraphs:
        words = len(para.split())
        current.append(para)
        current_words += words

        if current_words >= target_words:
            chunks.append(_make_chunk(current, team_name, source_type, source_url))
            current = []
            current_words = 0

    # leftover
    if current:
        chunks.append(_make_chunk(current, team_name, source_type, source_url))

    return chunks


def _make_chunk(paragraphs: list[str], team_name: str, source_type: str, source_url: str) -> Chunk:
    return Chunk(
        team_name=team_name,
        source_type=source_type,
        source_url=source_url,
        content="\n".join(paragraphs),
    )
