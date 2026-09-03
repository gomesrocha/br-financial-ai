from unittest.mock import Mock

from br_financial_ai.ai.llm import create_chat_model
from br_financial_ai.core.settings import Settings


def test_create_chat_model_uses_settings(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    chat_model = Mock(name="chat_model")

    def fake_init_chat_model(
        model: str,
        **kwargs: object,
    ) -> object:
        captured["model"] = model
        captured.update(kwargs)
        return chat_model

    monkeypatch.setattr(
        "br_financial_ai.ai.llm.init_chat_model",
        fake_init_chat_model,
    )

    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.1",
        llm_temperature=0,
    )

    result = create_chat_model(settings)

    assert result is chat_model
    assert captured["model"] == "llama3.1"
    assert captured["model_provider"] == "ollama"
    assert captured["temperature"] == 0
    assert "api_key" not in captured
