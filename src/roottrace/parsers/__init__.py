from __future__ import annotations

from importlib import metadata

from roottrace.parsers.base import LogParser
from roottrace.parsers.build_parser import MavenGradleParser
from roottrace.parsers.generic import GenericParser
from roottrace.parsers.jest_parser import JestParser
from roottrace.parsers.junit_parser import JUnitParser
from roottrace.parsers.pytest_parser import PytestParser

_BUILTINS: list[LogParser] = [JUnitParser(), PytestParser(), JestParser(), MavenGradleParser(), GenericParser()]


def _external_parsers() -> list[LogParser]:
    result: list[LogParser] = []
    try:
        eps = metadata.entry_points()
        group = eps.select(group="roottrace.parsers") if hasattr(eps, "select") else eps.get("roottrace.parsers", [])
        for ep in group:
            try:
                obj = ep.load()
                parser = obj() if isinstance(obj, type) else obj
                if isinstance(parser, LogParser):
                    result.append(parser)
            except Exception:
                continue
    except Exception:
        pass
    return result


def all_parsers() -> list[LogParser]:
    return [*_external_parsers(), *_BUILTINS]


def parser_names() -> list[str]:
    return [p.name for p in all_parsers()]


def select_parser(text: str, requested: str | None = None, source: str = "") -> LogParser:
    parsers = all_parsers()
    if requested:
        for parser in parsers:
            if parser.name == requested:
                return parser
        raise ValueError(f"Unknown parser: {requested}. Available: {', '.join(p.name for p in parsers)}")
    return max(parsers, key=lambda parser: parser.score(text, source))
