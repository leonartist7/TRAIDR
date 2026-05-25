"""Human explanations for deterministic score outputs."""

from __future__ import annotations

from collections.abc import Iterable


_REASON_TEXT = {
    "OPPORTUNITY_SCORE_V2_CALCULATED": "The score combines liquidity, volume, technicals, safety, data quality, and optional wallet, sentiment, and macro evidence.",
    "RUG_RISK_OPPORTUNITY_CAP": "High rug or safety risk capped the opportunity score.",
    "MISSING_SAFETY_CONFIDENCE_CAP": "Missing critical safety data capped confidence.",
    "LIQUIDITY_LOW_CAP": "Low liquidity capped the risk-adjusted score.",
    "LIQUIDITY_CRITICAL_CAP": "Critically low liquidity sharply capped the risk-adjusted score.",
    "HIGH_RISK_CAP": "High overall risk capped the risk-adjusted score.",
    "OPTIONAL_WALLET_SCORE_MISSING": "Wallet evidence was missing and did not add bullish weight.",
    "OPTIONAL_SENTIMENT_SCORE_MISSING": "Sentiment evidence was missing and did not add bullish weight.",
    "OPTIONAL_MACRO_SCORE_MISSING": "Macro evidence was missing and did not add bullish weight.",
}


def explain_reasons(reason_codes: Iterable[str]) -> str:
    """Return a compact plain-English explanation for reason codes."""

    reasons = tuple(dict.fromkeys(str(code) for code in reason_codes if code))
    if not reasons:
        return "No score reasons were available, so the model should be treated as non-actionable research."
    sentences = [_REASON_TEXT.get(reason, reason.replace("_", " ").lower().capitalize() + ".") for reason in reasons]
    sentences.append("This is research-only and cannot execute trades.")
    return " ".join(sentences)
