"""Small text vetoes, not a complete PII/PHI recognizer or de-identifier.

No negative match certifies safety. Approved public snapshots bypass these
heuristics; contextual views also require the independent model check.
"""
import re

PATTERNS = {
    "CONTACT": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "ID_NUMBER": re.compile(r"(?i)\b(?:mrn|empi|ssn|patient[_ ]?id|accession(?:[_ ]?number)?)\b[\"']?\s*[:=]\s*[\"']?[\w-]{2,}|\b\d{3}-\d{2}-\d{4}\b"),
    "DATE_OF_BIRTH": re.compile(r"(?i)\b(?:dob|birth[_ ]?date|date[_ ]?of[_ ]?birth)\b[\"']?\s*[:=]\s*[\"']?\d"),
    "CREDENTIAL": re.compile(r"(?i)\b(?:password|api[_ ]?key|access[_ ]?token|authorization)\b[\"']?\s*[:=]\s*[\"']?[^\s\"',}]{4,}"),
}


def categories(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in PATTERNS.items() if pattern.search(text))

