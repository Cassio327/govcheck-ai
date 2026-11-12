import asyncio

from govcheck.config import get_settings
from govcheck.infrastructure.embeddings.factory import build_embedding_provider


async def main() -> None:
    settings = get_settings()
    provider = build_embedding_provider(settings)
    vectors = await provider.embed_documents(["edital de licitação pública"])
    if len(vectors) != 1 or len(vectors[0]) != settings.embedding_dimension:
        raise RuntimeError("embedding smoke test returned an invalid shape")
    print(f"embedding_dimension={len(vectors[0])}")


if __name__ == "__main__":
    asyncio.run(main())
