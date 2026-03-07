from openai import OpenAI
from config import OPENROUTER_API_KEY
from internal_context.models import Chunk

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

BATCH_SIZE = 100
MODEL = "openai/text-embedding-3-small"


def embed_chunks(chunks: list[Chunk]) -> list[Chunk]:
    valid = [c for c in chunks if c.content.strip()]

    for i in range(0, len(valid), BATCH_SIZE):
        batch = valid[i:i + BATCH_SIZE]
        texts = [c.content for c in batch]
        res = client.embeddings.create(input=texts, model=MODEL)
        for j, item in enumerate(res.data):
            batch[j].embedding = item.embedding

    print(f"embedded {len(valid)} chunks ({len(chunks) - len(valid)} skipped empty)")
    return chunks
