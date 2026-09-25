from __future__ import annotations

import hashlib
import re

_VOLATILE = [
    (re.compile(r"0x[0-9a-f]+", re.I), "<hex>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ][0-9:.+Z-]+\b"), "<timestamp>"),
    (re.compile(r"\b[0-9a-f]{7,40}\b", re.I), "<sha>"),
    (re.compile(r"\b\d+\.\d+(?:\.\d+){0,2}\b"), "<version>"),
    (re.compile(r"\b\d+\b"), "<n>"),
    (re.compile(r"/tmp/[^\s]+|[A-Za-z]:\\\\[^\s]+"), "<path>"),
]


def normalize_message(message: str) -> str:
    text = " ".join(message.strip().split()).lower()
    for pattern, replacement in _VOLATILE:
        text = pattern.sub(replacement, text)
    return text[:500]


def make_fingerprint(
    category: str,
    subtype: str,
    exception: str | None,
    file: str | None,
    test: str | None,
    message: str,
) -> str:
    material = "|".join(
        [
            category.lower(),
            subtype.lower(),
            (exception or "").lower(),
            (file or "").replace("\\", "/").lower(),
            (test or "").lower(),
            normalize_message(message),
        ]
    )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:12].upper()
