# Five-minute product demo

1. In a Git repository, change a source file that is imported by a test.
2. Save a failing pytest/JUnit/Jest artifact.
3. Run `roottrace init`.
4. Run `roottrace analyze <artifact>` and show the normalized failure, fingerprint, Git evidence, probable cause, and reproduction command.
5. Run `roottrace impact` and show the affected dependent/test files.
6. Ingest repeated pass/fail JUnit artifacts and run `roottrace flaky`.
7. Run `roottrace report`, then `roottrace serve` to show the local history UI.
8. Show `.roottrace/reports/run-<id>.sarif` to demonstrate machine-readable CI integration.
9. Show `integrations/` to explain how RootTrace fits GitHub Actions, GitLab, or Jenkins without a RootTrace server.

The strongest interview explanation is not “AI finds bugs.” It is: RootTrace combines deterministic artifact parsing, history, Git evidence, dependency impact, and ranked hypotheses, while keeping proprietary engineering data local.
