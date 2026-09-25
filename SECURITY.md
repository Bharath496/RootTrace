# Security

Do not publish CI artifacts containing credentials or customer data when reporting a RootTrace issue. Redact secrets and proprietary paths before sharing.

RootTrace core is intended to make no network calls. A security report involving unexpected network behavior, unsafe report generation, command injection, or data leakage should be treated as high priority.

The optional Ollama integration executes the locally installed `ollama` program and should only be used with a trusted local installation and trusted model configuration.
