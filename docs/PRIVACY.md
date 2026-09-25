# Privacy and Security

RootTrace is local-first.

## Default behavior

- No RootTrace account.
- No telemetry.
- No remote database.
- No external AI API.
- No network requests in core analysis.
- State remains under the analyzed project's `.roottrace/` directory.

## Sensitive logs

CI artifacts can contain secrets, tokens, internal hostnames, customer data, and source paths. RootTrace stores the analyzed failure messages in local SQLite and reports. Teams should protect `.roottrace/` with the same controls used for build logs and should keep it out of version control; the provided `.gitignore` does so.

## SARIF

SARIF files can expose source paths and error messages. Uploading SARIF to another system is a user-controlled action and may transfer this information outside the machine.

## Optional Ollama integration

The `--ollama` feature invokes a locally installed Ollama executable. RootTrace does not download a model, start a remote service, or silently fall back to a hosted API. Users are responsible for how their own Ollama installation is configured.
