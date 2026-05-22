# Graphify

Graphify is an optional development-time repository analysis tool for TRAIDR. It is not a runtime dependency, and it must not be added to `requirements.txt` or `pyproject.toml` application dependencies.

## Purpose

Use Graphify to inspect code and docs as a knowledge graph while developing the local simulation engine. Graphify output does not participate in runtime risk, execution, storage, or prompt behavior.

## Optional Setup

Install Graphify outside TRAIDR's runtime dependency set. The upstream package name is `graphifyy`, while the CLI command is `graphify`.

```powershell
uv tool install graphifyy
graphify install --platform codex
```

Codex skill usage may use `$graphify .` after registration. In PowerShell, use the CLI form:

```powershell
graphify .
```

## Ignore Policy

The project root `.graphifyignore` excludes local environments, caches, generated storage, log output, DuckDB and Parquet data, and `.env` files from Graphify input:

```text
.venv/
__pycache__/
.pytest_cache/
storage/
logs/
*.duckdb
*.parquet
.env
```

Keep these exclusions in place when analyzing TRAIDR. In particular, do not include local database artifacts or environment files in repository analysis payloads.

## Safety Notes

- Graphify is optional and dev-only.
- Graphify must not change the deterministic risk engine or simulation execution boundary.
- Review upstream Graphify privacy and backend behavior before analyzing non-code assets or using headless extraction.
