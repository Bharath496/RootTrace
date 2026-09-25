from __future__ import annotations

from abc import ABC, abstractmethod

from roottrace.models import ParseResult


class LogParser(ABC):
    name = "base"

    @abstractmethod
    def score(self, text: str, source: str = "") -> int:
        """Return how strongly this parser recognizes the input."""

    @abstractmethod
    def parse(self, text: str, source: str = "") -> ParseResult:
        """Parse failures and test outcomes from the input."""
