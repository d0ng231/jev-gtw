"""Small text vetoes, not a complete PII/PHI recognizer or de-identifier.

No negative match certifies safety. Approved public snapshots bypass these
heuristics; contextual views also require the independent model check.
"""
import base64
import binascii
import html
import re
import unicodedata
from urllib.parse import unquote

PATTERNS = {
    "CONTACT": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "ID_NUMBER": re.compile(r"(?i)\b(?:mrn|empi|ssn|patient[_ ]?id|accession(?:[_ ]?number)?)\b[\"']?\s*[:=]\s*[\"']?[\w-]{2,}|\b\d{3}-\d{2}-\d{4}\b"),
    "DATE_OF_BIRTH": re.compile(r"(?i)\b(?:dob|birth[_ ]?date|date[_ ]?of[_ ]?birth)\b[\"']?\s*[:=]\s*[\"']?\d"),
    "CREDENTIAL": re.compile(r"(?i)\b(?:[a-z0-9]+[_-])?(?:password|passwd|api[_ ]?key|access[_ ]?token|authorization)\b[\"']?\s*[:=]\s*[\"']?(?P<value>[^\s\"',}]{4,})"),
}
BASE64 = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{16,4096}={0,2}(?![A-Za-z0-9+/_=-])")
UNICODE_ESCAPE = re.compile(r"\\u([0-9a-fA-F]{4})")
ENV_REFERENCE = re.compile(r"\$\{[A-Z_][A-Z0-9_]*\}")
MAX_NORMALIZED = 128_000


def _direct(text):
    found = set()
    # A literal environment reference contains no credential value. It still
    # receives model review; no regex non-match ever grants permission.
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            if name == "CREDENTIAL":
                reference = ENV_REFERENCE.match(text, match.start("value"))
                if reference and (reference.end() == len(text) or text[reference.end()] in " \t\r\n\"',}"):
                    continue
            found.add(name)
    return found


def _normalize(text):
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), text)
    return html.unescape(unquote(text, errors="replace"))


def categories(text: str) -> tuple[str, ...]:
    found = _direct(text)
    candidate = text
    # Bounded decoding handles common obfuscations without executing anything
    # or treating transformed bytes as an approved replacement view.
    for _ in range(2):
        if len(candidate) > MAX_NORMALIZED:
            found.add("ENCODING_LIMIT")
            break
        normalized = _normalize(candidate)
        if len(normalized) > MAX_NORMALIZED:
            found.add("ENCODING_LIMIT")
            break
        found.update(_direct(normalized))
        for index, match in enumerate(BASE64.finditer(normalized)):
            if index >= 32:
                found.add("ENCODING_LIMIT")
                break
            value = match.group()
            try:
                decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True).decode("utf-8")
            except (ValueError, UnicodeDecodeError, binascii.Error):
                continue
            signals = _direct(_normalize(decoded))
            if signals:
                found.update(signals)
                found.add("ENCODED_SENSITIVE")
        if normalized == candidate:
            break
        candidate = normalized
    return tuple(name for name in (*PATTERNS, "ENCODED_SENSITIVE", "ENCODING_LIMIT") if name in found)

