from govcheck.config import Settings
from govcheck.domain.llm import LLMProvider
from govcheck.infrastructure.llm.fake import FakeLLMProvider
from govcheck.infrastructure.llm.groq import GroqLLMProvider
from govcheck.infrastructure.llm.ollama import OllamaLLMProvider


class UnsupportedLLMProvider(ValueError):
    """Raised when configuration names an unknown provider."""


class MissingLLMCredential(ValueError):
    """Raised when a selected provider lacks its credential."""


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    if settings.llm_provider == "groq":
        if settings.groq_api_key is None:
            raise MissingLLMCredential("GROQ_API_KEY is required for Groq provider")
        return GroqLLMProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            base_url=settings.groq_base_url,
        )
    raise UnsupportedLLMProvider(f"Unsupported LLM provider: {settings.llm_provider}")
