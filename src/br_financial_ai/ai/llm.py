from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from br_financial_ai.core.settings import Settings, get_settings


def create_chat_model(
    settings: Settings | None = None,
) -> BaseChatModel:
    resolved = settings or get_settings()

    return init_chat_model(
        resolved.llm_model,
        model_provider=resolved.llm_provider,
        temperature=resolved.llm_temperature,
    )
