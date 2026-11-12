import hashlib
import math
from collections.abc import Sequence


class FakeEmbeddingProvider:
    """Deterministic, offline embeddings for tests and local smoke runs."""

    def __init__(
        self,
        *,
        dimension: int,
        forced_vectors: list[list[float]] | None = None,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        self.dimension = dimension
        self._forced_vectors = forced_vectors

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if self._forced_vectors is not None:
            return [vector.copy() for vector in self._forced_vectors]
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_documents([text]))[0]

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [
            ((digest[index % len(digest)] / 255.0) * 2) - 1 for index in range(self.dimension)
        ]
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / magnitude for value in vector]
