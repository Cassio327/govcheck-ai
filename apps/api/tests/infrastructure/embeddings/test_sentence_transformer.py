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


@pytest.mark.asyncio
async def test_e5_distinguishes_indexed_passages_from_search_queries() -> None:
    encoded_texts: list[list[str]] = []

    class RecordingTransformer:
        def encode(self, texts, *, normalize_embeddings, show_progress_bar):
            assert normalize_embeddings is True
            assert show_progress_bar is False
            encoded_texts.append(list(texts))
            return [[1.0, 0.0, 0.0] for _ in texts]

    provider = SentenceTransformerEmbeddingProvider(
        model_name="intfloat/multilingual-e5-small",
        dimension=3,
        model_loader=lambda _: RecordingTransformer(),
    )
    await provider.embed_documents(["O prazo consta na página 3."])
    query = await provider.embed_query("Qual é o prazo?")

    assert encoded_texts == [
        ["passage: O prazo consta na página 3."],
        ["query: Qual é o prazo?"],
    ]
    assert query == [1.0, 0.0, 0.0]


@pytest.mark.asyncio
async def test_non_e5_models_do_not_receive_e5_prefixes() -> None:
    encoded_texts: list[list[str]] = []

    class RecordingTransformer:
        def encode(self, texts, *, normalize_embeddings, show_progress_bar):
            encoded_texts.append(list(texts))
            return [[1.0, 0.0, 0.0] for _ in texts]

    provider = SentenceTransformerEmbeddingProvider(
        model_name="some-org/generic-embedding-model",
        dimension=3,
        model_loader=lambda _: RecordingTransformer(),
    )
    await provider.embed_documents(["documento"])
    await provider.embed_query("pergunta")
    assert encoded_texts == [["documento"], ["pergunta"]]
