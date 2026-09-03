import asyncio
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field, ValidationError, field_validator

from br_financial_ai.ai.llm import create_chat_model
from br_financial_ai.core.settings import get_settings
from br_financial_ai.domain.news_signals import (
    NEWS_CATEGORIES,
    NewsClassificationRequest,
    NewsMateriality,
    NewsRelevance,
    NewsSentiment,
    NewsSignal,
)
from br_financial_ai.observability.tracing import invoke_config
from br_financial_ai.observability.usage import (
    LlmUsage,
    unwrap_structured_output,
    usage_from_response,
)
from br_financial_ai.services.exceptions import (
    NewsClassificationError,
)

NEWS_CLASSIFIER_VERSION = 1
NEWS_CLASSIFIER_PROMPT_VERSION = "news-v1"

NEWS_CLASSIFIER_SYSTEM_PROMPT = """\
You classify a single company news article for later financial analysis.

Classify only from the provided title, summary, publisher, company name, \
and ticker. Do not invent company events, numbers, or facts that are not \
in the article text.

Relevance is how useful the article is for understanding this company. \
A sector or macro story can still be MEDIUM or HIGH relevance.

company_specific must be true only when the article reports facts, \
decisions, results, guidance, operations, or events of this company \
itself. If the company is merely mentioned among peers in a sector, \
commodity, or geopolitical story, company_specific must be false even \
when relevance is MEDIUM or HIGH.

Examples:
- "Petrobras announces new production guidance" → company_specific true, \
categories=production,capex.
- "Oil companies rise after a geopolitical event; Petrobras is mentioned \
among several companies" → company_specific false, \
categories=geopolitics,oil_price.

Materiality is the potential relevance of the content to the company's \
business or financial outlook. Sentiment is the likely directional \
business or financial implication. NEUTRAL is valid. Use MIXED when \
positive and negative implications are both present.

Always fill categories with the matching taxonomy keys when the article \
text supports them. For Strait of Hormuz, sanctions, war, or similar \
events use geopolitics. For crude or oil-sector price moves use \
oil_price and/or commodity_price. Do not force a category when evidence \
is weak. Uncertainty must reduce confidence.

Allowed categories:
earnings, revenue, profit, production, capex, debt, dividends, \
management, regulation, legal, governance, merger_acquisition, \
commodity_price, oil_price, interest_rates, currency, geopolitics, \
macro, operations, accident, environment.
"""


class NewsClassificationOutput(BaseModel):
    relevance: Literal["LOW", "MEDIUM", "HIGH"]
    materiality: Literal["LOW", "MEDIUM", "HIGH"]
    sentiment: Literal["NEGATIVE", "NEUTRAL", "POSITIVE", "MIXED"]
    company_specific: bool
    categories: str = Field(
        description=(
            "Comma-separated taxonomy keys. Example: geopolitics,oil_price. "
            "Use geopolitics for Hormuz, war, or sanctions. Use oil_price or "
            "commodity_price for crude or sector price moves. Use empty "
            "string only if no taxonomy key applies."
        ),
    )
    confidence: float = Field(ge=0, le=1)
    rationale: str

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value if str(item).strip())

        return str(value).strip()


def create_news_classifier(
    model: BaseChatModel | None = None,
) -> "NewsClassifier":
    resolved = model or create_chat_model()

    return NewsClassifier(
        structured_model=resolved.with_structured_output(
            NewsClassificationOutput,
            include_raw=True,
        )
    )


def news_signal_from_output(
    article_id: int | None,
    output: NewsClassificationOutput,
) -> NewsSignal:
    return NewsSignal(
        article_id=article_id,
        relevance=NewsRelevance(output.relevance),
        materiality=NewsMateriality(output.materiality),
        sentiment=NewsSentiment(output.sentiment),
        company_specific=output.company_specific,
        categories=_parse_category_keys(output.categories),
        confidence=Decimal(str(output.confidence)),
        rationale=output.rationale,
    )


def parse_news_classification_output(
    article_id: int | None,
    payload: object,
) -> NewsSignal:
    try:
        output = (
            payload
            if isinstance(payload, NewsClassificationOutput)
            else NewsClassificationOutput.model_validate(payload)
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise NewsClassificationError("Malformed news classification result.") from exc

    if output.confidence < 0 or output.confidence > 1:
        raise NewsClassificationError("Classification confidence is out of range.")

    return news_signal_from_output(article_id, output)


def _parse_category_keys(raw: str) -> tuple[str, ...]:
    return tuple(
        category
        for category in (part.strip() for part in raw.replace(";", ",").split(","))
        if category in NEWS_CATEGORIES
    )


class NewsClassifier:
    def __init__(
        self,
        structured_model: Runnable,
        *,
        concurrency: int | None = None,
    ) -> None:
        self._structured_model = structured_model
        self._concurrency = concurrency
        self.last_usage: LlmUsage | None = None

    def fork(self) -> "NewsClassifier":
        return NewsClassifier(self._structured_model, concurrency=1)

    def classification_concurrency(self) -> int:
        configured = (
            self._concurrency
            if self._concurrency is not None
            else get_settings().news_classification_concurrency
        )
        return max(1, min(16, int(configured)))

    async def classify(
        self,
        request: NewsClassificationRequest,
    ) -> NewsSignal:
        messages = [
            SystemMessage(content=NEWS_CLASSIFIER_SYSTEM_PROMPT),
            HumanMessage(content=_article_prompt(request)),
        ]

        try:
            payload = await self._structured_model.ainvoke(
                messages,
                config=invoke_config("news_classification"),
            )
            self.last_usage = usage_from_response(payload)
            parsed, _raw = unwrap_structured_output(payload)
        except NewsClassificationError:
            raise
        except Exception as exc:
            raise NewsClassificationError("Failed to classify news article.") from exc

        return parse_news_classification_output(
            request.article_id,
            parsed,
        )

    async def classify_many(
        self,
        requests: Sequence[NewsClassificationRequest],
    ) -> list[NewsSignal | None]:
        if not requests:
            return []

        semaphore = asyncio.Semaphore(self.classification_concurrency())

        async def classify_one(
            request: NewsClassificationRequest,
        ) -> NewsSignal | None:
            async with semaphore:
                try:
                    return await self.classify(request)
                except NewsClassificationError:
                    return None

        return list(await asyncio.gather(*(classify_one(item) for item in requests)))


def _article_prompt(request: NewsClassificationRequest) -> str:
    summary = request.summary.strip() if request.summary else ""
    publisher = request.publisher.strip() if request.publisher else ""

    return (
        f"Ticker: {request.ticker.strip().upper()}\n"
        f"Company: {request.company_name.strip()}\n"
        f"Title: {request.title.strip()}\n"
        f"Publisher: {publisher or '(unknown)'}\n"
        f"Summary: {summary or '(none)'}\n"
    )
