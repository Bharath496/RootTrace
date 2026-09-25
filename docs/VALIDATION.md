# Validation Strategy

A developer tool needs evidence that it works on more than handcrafted happy paths.

## Included checks

The automated suite covers:

- fingerprint stability under volatile numbers;
- pytest failure and test-outcome extraction;
- JUnit pass/fail/skip extraction;
- Jest failure extraction;
- Maven/Gradle compilation classification;
- generic infrastructure classification;
- pass/fail-history flaky scoring;
- Python reverse-dependency impact traversal;
- generation of JSON, Markdown, HTML, and SARIF reports.

The bundled benchmark checks parser/classification behavior across five artifact families.

## Real-world evaluation plan

For serious claims, build a corpus from public repositories containing historical failed CI artifacts and manually label:

- failure family;
- root-cause file when known;
- recurrence equivalence;
- flaky/non-flaky status where rerun evidence exists.

Measure classification precision/recall, fingerprint grouping quality, root-cause top-k accuracy, flaky precision/recall, analysis runtime, and memory use. Publish the corpus selection method and ambiguous cases. Do not call a feature “accurate” based only on bundled fixtures.
