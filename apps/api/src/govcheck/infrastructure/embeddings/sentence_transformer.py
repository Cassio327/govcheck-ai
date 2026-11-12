import asyncio
from collections.abc import Callable, Sequence
from typing import Any


class EmbeddingDimensionError(RuntimeError):
    """Raised when a loaded model does not match the configured vector column."""


def _load_sentence_transformer(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class SentenceTransformerEmbeddingProvider:
    def __init__(
        self,
        *,
        model_name: str,
        dimension: int,
        model_loader: Callable[[str], Any] = _load_sentence_transformer,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be greater than zero")
        self.model_name = model_name
        model_id = model_name.rsplit("/", 1)[-1].casefold()
        self._e5 = (
            model_id.startswith(("e5-", "multilingual-e5-")) and "instruct" not in model_id
        )
        self.dimension = dimension
        self._model_loader = model_loader
        self._model: Any | None = None
        self._load_lock = asyncio.Lock()

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    async def _get_model(self) -> Any:
        if self._model is None:
            async with self._load_lock:
                if self._model is None:
                    self._model = await asyncio.to_thread(self._model_loader, self.model_name)
        return self._model

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        values = [f"passage: {text}" for text in texts] if self._e5 else list(texts)
        return await self._embed(values)

    async def embed_query(self, text: str) -> list[float]:
        """Use a retrieval-query prefix for non-instruct E5 models."""
        values = [f"query: {text}" if self._e5 else text]
        vectors = await self._embed(values)
        return vectors[0]

    async def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = await self._get_model()
        encoded = await asyncio.to_thread(
            model.encode,
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        raw_vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        vectors = [[float(value) for value in vector] for vector in raw_vectors]
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingDimensionError(
                    f"expected dimension {self.dimension}, received {len(vector)}"
                )
        return vectors
