"""FAQ search service helpers using JSON files (no DB)."""

from core.json_data import load_json
from core.exceptions import NotFoundError, ServiceError, ValidationError
import logging
import re

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


def _normalize_text(value):
    text = (value or "").strip().lower()
    text = re.sub(r"[^\w\u0900-\u097F]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    query_norm = _normalize_text(normalized_query)

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
        question_norm = _normalize_text(question)
        text_norm = _normalize_text(text_blob)

        # base similarity
        score = _similarity(query_norm, text_norm)

        # Exact or near-exact question matches should always win over keyword overlap.
        if query_norm and query_norm == question_norm:
            score = 1.1
        elif query_norm and (query_norm in question_norm or question_norm in query_norm):
            score = max(score, 1.05)

        # boost only when the same keyword appears in both the query and the FAQ record
        keyword_hit = any(
            kw in q_lower and kw in text_blob.lower()
            for kw in KEYWORD_TERMS
        )
        substring_hit = query_norm in text_norm or text_norm in query_norm
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
