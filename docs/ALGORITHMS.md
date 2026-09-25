# Algorithms

## Failure normalization and fingerprinting

A fingerprint combines normalized category, subtype, exception, file, test name, and message. Volatile values such as timestamps, raw numbers, hexadecimal addresses, versions, temporary paths, and commit-looking hashes are normalized before hashing. The goal is to group recurring signatures without collapsing unrelated failures into one bucket.

## Flaky score

RootTrace records test outcomes over time. For a test with both passes and failures, the score combines:

- outcome balance: how much both pass and fail outcomes exist;
- transition rate: how frequently the state changes between adjacent recorded outcomes.

A test that always fails is not called flaky merely because it fails often. A test that alternates between pass and fail receives a high score. This is a heuristic indicator, not a statistical proof of nondeterminism.

## Root-cause ranking

Candidates receive evidence from:

- direct changed-file match with the failure location;
- changed file appearing in the stack trace;
- module/name token overlap with the error/test;
- normalized failure family such as dependency, CI secret, DNS, database, auth, or compilation;
- recent Git history for correlated files.

The resulting score is a prioritization aid. RootTrace intentionally calls these **probable causes**, not verified causes.

## Change impact

RootTrace builds an import graph using:

- Python `ast` imports;
- JavaScript/TypeScript relative import/require statements;
- Java imports indexed by class name.

The graph is reversed and breadth-first traversal starts at the changed files. Distance 0 is directly changed, distance 1 directly depends on a changed file, and so on. Test-like files in the impacted set are surfaced as candidate tests.

Dynamic imports, reflection, generated code, runtime service relationships, and build-tool-specific dependency semantics are outside V1's static graph and therefore produce false negatives in some codebases.
