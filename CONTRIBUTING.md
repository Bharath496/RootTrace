# Contributing

1. Create a branch.
2. Add or update tests for behavior changes.
3. Run `PYTHONPATH=src python -m unittest discover -s tests -v`.
4. Run `PYTHONPATH=src python -m roottrace.cli benchmark benchmarks/manifest.json`.
5. Keep core functionality offline and dependency-light.
6. Do not increase root-cause confidence without adding concrete evidence.

For a new parser, subclass `roottrace.parsers.base.LogParser` and implement `score()` and `parse()`. External packages can register a parser under the `roottrace.parsers` entry-point group.
