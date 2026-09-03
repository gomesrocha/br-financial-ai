from br_financial_ai.core.settings import Settings, cors_origin_list


def test_cors_origins_default_to_local_frontend() -> None:
    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.1",
        llm_temperature=0,
    )

    assert cors_origin_list(settings) == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_cors_origins_are_parsed_from_comma_separated_list() -> None:
    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.1",
        llm_temperature=0,
        cors_origins="http://localhost:3000, http://127.0.0.1:3000",
    )

    assert cors_origin_list(settings) == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_empty_cors_origins_disable_cross_origin_list() -> None:
    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.1",
        llm_temperature=0,
        cors_origins="",
    )

    assert cors_origin_list(settings) == []


def test_news_classification_concurrency_defaults_to_three() -> None:
    settings = Settings(
        llm_provider="ollama",
        llm_model="llama3.1",
        llm_temperature=0,
    )

    assert settings.news_classification_concurrency == 3
