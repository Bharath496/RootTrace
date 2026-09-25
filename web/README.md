# RootTrace public site

This directory is intentionally separate from the RootTrace analysis engine.

The core product remains local-first. This folder contains only a static public product/portfolio site and can be hosted on Vercel without moving logs, source code analysis, SQLite history, or CI artifacts into a hosted RootTrace service.

## Vercel

Create a Vercel project from this GitHub repository and set **Root Directory** to `web`.

- Framework preset: Other / static
- Build command: none
- Output directory: `.`
- Environment variables: none required

The site itself has no backend and requires no paid API.
