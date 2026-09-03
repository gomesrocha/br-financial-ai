from decimal import Decimal
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel, Field, ValidationError

from br_financial_ai.ai.llm import create_chat_model
from br_financial_ai.ai.recommendation_prompt import (
    RecommendationPromptContext,
    build_recommendation_prompt_context,
)
from br_financial_ai.domain.analysis import (
    RecommendationContext,
)
from br_financial_ai.domain.recommendation import (
    RecommendationResult,
    RecommendationStance,
    evidence_identity,
    limitations_from_context,
)
from br_financial_ai.eval.factual import evaluate_factual_consistency
from br_financial_ai.observability.tracing import invoke_config
from br_financial_ai.observability.usage import (
    LlmUsage,
    merge_usage,
    unwrap_structured_output,
    usage_from_response,
)
from br_financial_ai.services.exceptions import (
    RecommendationGenerationError,
)

RECOMMENDATION_SYSTEM_PROMPT = """\
You produce a structured analytical outlook for one Brazilian listed \
company from a supplied RecommendationContext.

Analyze ONLY the supplied context. Never invent financial or market \
values. Never introduce facts, events, URLs, or sources that are not \
present in the context. Do not recalculate or replace deterministic \
inputs such as CVM financials, margins, P/S, P/E, price, market cap, \
returns, volatility, drawdown, news metadata, or NewsSignal labels.

Consider fundamentals, valuation, market behavior, and news separately. \
Explain contradictions between those signals. Preserve uncertainty. \
Mention important unavailable information from the supplied limitations \
and unavailable sections. Do not treat unavailable metrics as zero.

Stance must be exactly one of FAVORABLE, NEUTRAL, or UNFAVORABLE.
Do not use BUY, SELL, HOLD, STRONG_BUY, or STRONG_SELL.
This is an analytical outlook, not personalized financial advice.

When restating BRL amounts, copy the JSON digits or use the supplied \
amount_scales.million / amount_scales.billion strings exactly. \
Do not drop digits when converting to million or billion.

Metrics listed as unsupported or unavailable may be discussed only \
as unavailable. Never provide a numeric value for them.

FAVORABLE means the available evidence is predominantly constructive.
NEUTRAL means evidence is mixed or insufficient.
UNFAVORABLE means the available evidence is predominantly adverse.
Do not base the stance on a single metric.

Confidence is a number from 0 to 1 reflecting completeness of the \
context, agreement or conflict among evidence, unavailable sections, \
and uncertainty. It is not a probability that the price will rise.

If you include evidence items, copy source, kind, and reference \
exactly from the supplied context. Do not fabricate identifiers.

Write summary and views in English. Keep them concise.
"""


class RecommendationEvidenceOutput(BaseModel):
    source: str
    kind: str
    reference: str


class RecommendationModelOutput(BaseModel):
    ticker: str
    stance: Literal["FAVORABLE", "NEUTRAL", "UNFAVORABLE"]
    confidence: float = Field(ge=0, le=1)
    summary: str
    positives: list[str]
    risks: list[str]
    fundamentals_view: str
    valuation_view: str
    market_view: str
    news_view: str
    evidence: list[RecommendationEvidenceOutput] = Field(
        default_factory=list,
    )


def create_recommendation_engine(
    model: BaseChatModel | None = None,
) -> "RecommendationEngine":
    resolved = model or create_chat_model()

    return RecommendationEngine(
        structured_model=resolved.with_structured_output(
            RecommendationModelOutput,
            include_raw=True,
        )
    )


def parse_recommendation_output(
    context: RecommendationContext,
    payload: object,
) -> RecommendationResult:
    try:
        output = (
            payload
            if isinstance(payload, RecommendationModelOutput)
            else RecommendationModelOutput.model_validate(payload)
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise RecommendationGenerationError("Malformed recommendation result.") from exc

    return recommendation_from_output(context, output)


def recommendation_from_output(
    context: RecommendationContext,
    output: RecommendationModelOutput,
) -> RecommendationResult:
    if output.ticker.strip().upper() != context.ticker:
        raise RecommendationGenerationError(
            "Recommendation ticker does not match the context."
        )

    try:
        stance = RecommendationStance(output.stance)
    except ValueError as exc:
        raise RecommendationGenerationError(
            "Unsupported recommendation stance."
        ) from exc

    confidence = Decimal(str(output.confidence))

    if confidence < 0 or confidence > 1:
        raise RecommendationGenerationError(
            "Recommendation confidence is out of range."
        )

    summary = output.summary.strip()
    fundamentals_view = output.fundamentals_view.strip()
    valuation_view = output.valuation_view.strip()
    market_view = output.market_view.strip()
    news_view = output.news_view.strip()

    if not summary:
        raise RecommendationGenerationError("Recommendation summary is empty.")

    if not fundamentals_view:
        raise RecommendationGenerationError("Fundamentals view is empty.")

    if not valuation_view:
        raise RecommendationGenerationError("Valuation view is empty.")

    if not market_view:
        raise RecommendationGenerationError("Market view is empty.")

    if not news_view:
        raise RecommendationGenerationError("News view is empty.")

    allowed_evidence = {evidence_identity(item) for item in context.evidence}

    for item in output.evidence:
        identity = (item.source, item.kind, item.reference)

        if identity not in allowed_evidence:
            raise RecommendationGenerationError(
                "Recommendation referenced evidence that is not in the context."
            )

    return RecommendationResult(
        ticker=context.ticker,
        stance=stance,
        confidence=confidence,
        summary=summary,
        positives=tuple(item.strip() for item in output.positives if item.strip()),
        risks=tuple(item.strip() for item in output.risks if item.strip()),
        fundamentals_view=fundamentals_view,
        valuation_view=valuation_view,
        market_view=market_view,
        news_view=news_view,
        limitations=limitations_from_context(context),
        evidence=context.evidence,
        as_of=context.as_of,
    )


class RecommendationEngine:
    def __init__(
        self,
        structured_model: Runnable,
    ) -> None:
        self._structured_model = structured_model
        self.last_usage: LlmUsage | None = None
        self.last_prompt: RecommendationPromptContext | None = None

    def fork(self) -> "RecommendationEngine":
        return RecommendationEngine(self._structured_model)

    async def generate_recommendation(
        self,
        context: RecommendationContext,
    ) -> RecommendationResult:
        self.last_prompt = build_recommendation_prompt_context(context)
        messages = [
            SystemMessage(content=RECOMMENDATION_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "RecommendationContext JSON follows. Use these values as given.\n"
                    f"{self.last_prompt.serialized}"
                )
            ),
        ]

        self.last_usage = None
        try:
            parsed = await self._invoke(messages)
            result, rewrite = self._first_pass_result(context, parsed)
            if rewrite is None:
                if result is None:
                    raise RecommendationGenerationError(
                        "Failed to generate recommendation."
                    )
                return result

            messages.append(HumanMessage(content=rewrite))
            parsed = await self._invoke(messages)
            return parse_recommendation_output(context, parsed)
        except RecommendationGenerationError:
            raise
        except Exception as exc:
            raise RecommendationGenerationError(
                "Failed to generate recommendation."
            ) from exc

    async def _invoke(self, messages: list) -> object:
        payload = await self._structured_model.ainvoke(
            messages,
            config=invoke_config("recommendation_generation"),
        )
        self.last_usage = merge_usage(
            self.last_usage,
            usage_from_response(payload),
        )
        parsed, _raw = unwrap_structured_output(payload)
        return parsed

    def _first_pass_result(
        self,
        context: RecommendationContext,
        parsed: object,
    ) -> tuple[RecommendationResult | None, str | None]:
        try:
            result = parse_recommendation_output(context, parsed)
        except RecommendationGenerationError as exc:
            if "not in the context" not in str(exc):
                raise
            return None, (
                "The previous draft cited evidence that is not in the "
                "context. Copy source, kind, and reference exactly from "
                "the JSON evidence list. Do not invent sources."
            )

        factual = evaluate_factual_consistency(context, result)
        if not factual.inconsistent_claims:
            return result, None

        return result, (
            "The previous draft used numeric fragments that are not "
            "grounded in the context: "
            f"{', '.join(factual.inconsistent_claims)}. "
            "Rewrite using the JSON amounts and amount_scales exactly. "
            "Do not drop digits when converting to million or billion."
        )
