import pytest
from pydantic import SecretStr

from govcheck.config import Settings
from govcheck.infrastructure.llm.factory import (
    UnsupportedLLMProvider,
    build_llm_provider,
)
from govcheck.infrastructure.llm.fake import FakeLLMProvider
from govcheck.infrastructure.llm.groq import GroqLLMProvider
from govcheck.infrastructure.llm.ollama import OllamaLLMProvider


def test_factory_builds_fake_provider_without_external_client() -> None:
    provider = build_llm_provider(Settings(llm_provider="fake"))

    assert isinstance(provider, FakeLLMProvider)


def test_factory_builds_lazy_ollama_provider() -> None:
    provider = build_llm_provider(
        Settings(llm_provider="ollama", ollama_base_url="http://localhost:11434")
    )

    assert isinstance(provider, OllamaLLMProvider)
    assert provider.client_created is False


def test_factory_builds_lazy_groq_provider_without_exposing_secret() -> None:
    secret = "gsk_do-not-print-this-value"
    provider = build_llm_provider(Settings(llm_provider="groq", groq_api_key=SecretStr(secret)))

    assert isinstance(provider, GroqLLMProvider)
    assert provider.client_created is False
    assert secret not in repr(provider)


def test_factory_rejects_unknown_provider_without_echoing_settings() -> None:
    settings = Settings().model_copy(update={"llm_provider": "unknown"})

    with pytest.raises(UnsupportedLLMProvider, match="Unsupported LLM provider: unknown"):
        build_llm_provider(settings)
