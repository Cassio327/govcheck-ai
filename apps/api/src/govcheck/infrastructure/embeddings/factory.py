from govcheck.config import Settings
from govcheck.domain.retrieval import EmbeddingProvider
from govcheck.infrastructure.embeddings.fake import FakeEmbeddingProvider
from govcheck.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)


class UnsupportedEmbeddingProvider(ValueError):
    """Raised when configuration names an unknown provider."""


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "fake":
        return FakeEmbeddingProvider(dimension=settings.embedding_dimension)
    if settings.embedding_provider == "sentence-transformer":
        return SentenceTransformerEmbeddingProvider(
            model_name=settings.embedding_model,
            dimension=settings.embedding_dimension,
        )
    raise UnsupportedEmbeddingProvider(
        f"Unsupported embedding provider: {settings.embedding_provider}"
    )
