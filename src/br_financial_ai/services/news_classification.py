from dataclasses import dataclass, replace
from datetime import UTC, datetime

from br_financial_ai.ai.news_classifier import (
    NEWS_CLASSIFIER_PROMPT_VERSION,
    NEWS_CLASSIFIER_VERSION,
    NewsClassifier,
)
from br_financial_ai.core.settings import Settings, get_settings
from br_financial_ai.db.models import NewsArticleSignal
from br_financial_ai.domain.analysis import (
    RecommendationContext,
    UnavailableSection,
)
from br_financial_ai.domain.news_signals import (
    NewsClassificationRequest,
    NewsClassifierIdentity,
    NewsMateriality,
    NewsRelevance,
    NewsSentiment,
    NewsSignal,
)
from br_financial_ai.repositories.news_article_signal import (
    NewsArticleSignalRepository,
)


@dataclass(frozen=True, slots=True)
class NewsClassificationStats:
    article_count: int
    cache_hits: int
    cache_misses: int
    classified: int
    failed: int


def classifier_identity_from_settings(
    settings: Settings | None = None,
) -> NewsClassifierIdentity:
    resolved = settings or get_settings()
    return NewsClassifierIdentity(
        model_provider=resolved.llm_provider,
        model_name=resolved.llm_model,
        classifier_version=NEWS_CLASSIFIER_VERSION,
        prompt_version=NEWS_CLASSIFIER_PROMPT_VERSION,
    )


def news_signal_from_record(row: NewsArticleSignal) -> NewsSignal:
    return NewsSignal(
        article_id=row.news_article_id,
        relevance=NewsRelevance(row.relevance),
        materiality=NewsMateriality(row.materiality),
        sentiment=NewsSentiment(row.sentiment),
        company_specific=row.company_specific,
        categories=tuple(row.categories),
        confidence=row.confidence,
        rationale=row.rationale,
    )


class NewsClassificationService:
    def __init__(
        self,
        repository: NewsArticleSignalRepository,
        classifier: NewsClassifier,
        *,
        identity: NewsClassifierIdentity | None = None,
    ) -> None:
        self.repository = repository
        self.classifier = classifier
        self.identity = identity or classifier_identity_from_settings()
        self.last_stats: NewsClassificationStats | None = None

    async def load_cached_signals(
        self,
        article_ids: list[int],
    ) -> dict[int, NewsSignal]:
        rows = await self.repository.list_by_article_ids_and_identity(
            article_ids,
            self.identity,
        )
        return {
            article_id: news_signal_from_record(row) for article_id, row in rows.items()
        }

    async def enrich_context(
        self,
        context: RecommendationContext,
    ) -> RecommendationContext:
        article_ids = [
            item.article_id
            for item in context.recent_news
            if item.article_id is not None
        ]
        cached = await self.load_cached_signals(article_ids)
        missing_items = [
            item
            for item in context.recent_news
            if item.article_id is not None and item.article_id not in cached
        ]

        classified = 0
        failed = 0
        unavailable = list(context.unavailable)
        persisted = dict(cached)

        if missing_items:
            requests = [
                NewsClassificationRequest(
                    article_id=item.article_id,
                    ticker=context.ticker,
                    company_name=context.company_name,
                    title=item.title,
                    summary=item.summary,
                    publisher=item.publisher,
                )
                for item in missing_items
            ]
            outcomes = await self.classifier.classify_many(requests)
            classified_at = datetime.now(UTC)

            for item, signal in zip(missing_items, outcomes, strict=True):
                if signal is None:
                    failed += 1
                    unavailable.append(
                        UnavailableSection(
                            section="news_classification",
                            source="LLM",
                            reason="classification_failed",
                            reference=(
                                str(item.article_id)
                                if item.article_id is not None
                                else item.canonical_url
                            ),
                        )
                    )
                    continue

                await self.repository.upsert_signal(
                    signal,
                    self.identity,
                    classified_at=classified_at,
                )
                persisted[signal.article_id or item.article_id] = signal
                classified += 1

        ordered = [
            persisted[item.article_id]
            for item in context.recent_news
            if item.article_id is not None and item.article_id in persisted
        ]
        self.last_stats = NewsClassificationStats(
            article_count=len(context.recent_news),
            cache_hits=len(cached),
            cache_misses=len(missing_items),
            classified=classified,
            failed=failed,
        )
        return replace(
            context,
            news_signals=tuple(ordered),
            unavailable=tuple(unavailable),
        )
