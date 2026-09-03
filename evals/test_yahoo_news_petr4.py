import pytest

from br_financial_ai.clients.yahoo_news import YahooNewsClient
from br_financial_ai.domain.news import NewsArticleRecord

pytestmark = [pytest.mark.eval, pytest.mark.external, pytest.mark.yahoo]


@pytest.mark.asyncio
async def test_yahoo_news_returns_normalized_petr4_article() -> None:
    client = YahooNewsClient()

    articles = await client.get_company_news("PETR4", limit=5)

    assert articles
    assert all(isinstance(article, NewsArticleRecord) for article in articles)

    article = articles[0]

    assert article.yahoo_symbol == "PETR4.SA"
    assert article.title
    assert article.url
    assert article.published_at.tzinfo is not None

    print(article)
