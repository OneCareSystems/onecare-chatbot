"""CHAT-05: knowledge-gap decision. RULE (documented, inclusive): the best score must be >= the threshold of the QUERY
language. A score exactly at the threshold IS a match. Scores are compared rounded to 4 decimals (float32 noise)."""
from django.conf import settings


def threshold_for(language):
    thresholds = getattr(settings, "CHAT_SCORE_THRESHOLDS", {})
    return thresholds.get(language if language in ("EN", "TA") else "DEFAULT", thresholds.get("DEFAULT", 0.8))


def best_score(hits):
    return max((hit["score"] for hit in hits), default=None)


def is_confident(hits, language):
    """False for no hits at all (empty knowledge base) and for a best score below the threshold."""
    best = best_score(hits)
    if best is None:
        return False
    return round(best, 4) >= round(threshold_for(language), 4)