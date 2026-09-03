from langchain_core.runnables import RunnableConfig


def tracing_enabled() -> bool:
    from os import getenv

    return getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in {
        "1",
        "true",
        "yes",
    } or getenv("LANGSMITH_TRACING", "").strip().lower() in {"1", "true", "yes"}


def invoke_config(run_name: str) -> RunnableConfig:
    return RunnableConfig(
        run_name=run_name,
        tags=["br-financial-ai", run_name],
        metadata={"component": run_name},
    )
