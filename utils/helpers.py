"""Small, pure helper functions shared across agents."""

import re
from datetime import datetime, timedelta, timezone

_FILLER_WORDS = {
    "for", "and", "the", "a", "an", "in", "on", "with", "about",
    "how", "to", "of", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "shall",
}

_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.DOTALL)
_URL_RE = re.compile(r"https?://[^\s)]+")


def strip_code_fence(text: str) -> str:
    return re.sub(r"```json|```", "", text).strip()


def extract_json_array(text: str | None) -> list:
    """Parses a JSON array out of an LLM response, tolerating markdown fences and stray prose."""
    import json

    if not text:
        return []

    cleaned = strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = _JSON_ARRAY_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    return []


def extract_key_terms(topic: str, max_terms: int = 3) -> str:
    """Reduces a topic to its 1-3 most meaningful words, for use as a search query."""
    words = topic.lower().split()
    key_words = [w for w in words if w not in _FILLER_WORDS and len(w) > 2]
    terms = key_words[:max_terms]
    return " ".join(terms) if terms else topic


def extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    match = _URL_RE.search(text)
    return match.group(0) if match else None


def days_ago_iso(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()


def strip_code_block(text: str) -> str:
    cleaned = re.sub(r"^```(text|markdown)?", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned)
    return cleaned.strip()
