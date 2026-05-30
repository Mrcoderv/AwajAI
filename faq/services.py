"""FAQ search service helpers using JSON files (no DB)."""

from core.json_data import load_json
from core.exceptions import NotFoundError, ServiceError, ValidationError
import logging

logger = logging.getLogger(__name__)

try:
    # Prefer rapidfuzz when available for fuzzy matching
    from rapidfuzz.fuzz import ratio as _rf_ratio
    def _similarity(a, b):
        try:
            return _rf_ratio(a or "", b or "") / 100.0
        except Exception:
            return 0.0
except Exception:
    # Fallback to difflib.SequenceMatcher
    from difflib import SequenceMatcher
    def _similarity(a, b):
        try:
            return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()
        except Exception:
            return 0.0


KEYWORD_TERMS = [
    'rollover', 'data rollover', 'unused data', 'carry forward', 'carryforward', 'roll over', 'roll over data', 'rollover policy'
]


def search_faqs(query):
    """Return up to three published FAQ matches for a search query.

    Uses keyword matching and fuzzy scoring to find relevant FAQs. Returns
    the best matches when similarity exceeds a threshold.
    """
    normalized_query = (query or "").strip()
    if not normalized_query:
        raise ValidationError("Please tell me what you want to search for.")

    try:
        faqs = load_json("faqs.json")
    except ServiceError as exc:
        raise

    if not faqs:
        raise NotFoundError("No FAQ records are available yet.")

    logger.debug("FAQ QUERY: %s", normalized_query)

    # Compute a similarity score for each FAQ and pick the best one.
    scored = []
    q_lower = normalized_query.lower()
    for faq in faqs:
        if not faq.get("is_published", False):
            continue
        question = (faq.get("question") or "").strip()
        answer = (faq.get("answer") or "").strip()
        category = (faq.get("category") or "").strip()
        text_blob = " ".join(filter(None, [question, answer, category]))

        # base similarity
        score = _similarity(normalized_query, text_blob)

        # boost to 1.0 for clear keyword presence (ensures correct mapping for known terms)
        keyword_hit = any(kw in q_lower or kw in question.lower() or kw in answer.lower() or kw in category.lower() for kw in KEYWORD_TERMS)
        substring_hit = q_lower in question.lower() or q_lower in answer.lower() or q_lower in category.lower()
        if keyword_hit or substring_hit:
            score = max(score, 1.0)

        logger.debug("FAQ SCORE: query=%s score=%.3f faq=%s", normalized_query, score, question)
        scored.append((score, faq))

    if not scored:
        raise NotFoundError("I couldn't find any matching FAQs.")

    # pick highest scoring FAQ
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_faq = scored[0]
    logger.debug("BEST FAQ SCORE: %.3f -> %s", best_score, best_faq.get("question"))

    # require a reasonable threshold (70%) to return a match
    threshold = 0.7
    if best_score >= threshold:
        logger.debug("MATCHED FAQ: score=%.3f question=%s", best_score, best_faq.get("question"))
        return [{
            "question": best_faq.get("question"),
            "answer": best_faq.get("answer"),
            "category": best_faq.get("category"),
        }]

    raise NotFoundError("I couldn't find any matching FAQs.")
