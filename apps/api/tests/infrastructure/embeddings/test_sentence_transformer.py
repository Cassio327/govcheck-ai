import pytest

from govcheck.infrastructure.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)


class StubSentenceTransformer:
    def encode(self, texts, *, normalize_embeddings, show_progress_bar):
        assert normalize_embeddings is True
        assert show_progress_bar is False
        return [[float(index), 0.0, 1.0] for index, _ in enumerate(texts)]


@pytest.mark.asyncio
async def test_sentence_transformer_adapter_loads_model_only_on_first_embedding() -> None:
    loaded_models: list[str] = []

    def loader(model_name: str):
        loaded_models.append(model_name)
        return StubSentenceTransformer()

    provider = SentenceTransformerEmbeddingProvider(
        model_name="intfloat/multilingual-e5-small",
        dimension=3,
        model_loader=loader,
    )

    assert provider.model_loaded is False
    first = await provider.embed_documents(["edital", "prazo"])
    second = await provider.embed_documents(["sanção"])

    assert first == [[0.0, 0.0, 1.0], [1.0, 0.0, 1.0]]
    assert second == [[0.0, 0.0, 1.0]]
    assert loaded_models == ["intfloat/multilingual-e5-small"]
    assert provider.model_loaded is True
