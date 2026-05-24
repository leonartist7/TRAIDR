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

If the user Python Scripts directory is not on PATH, use the module form instead:

```powershell
python -m pip install --user graphifyy
python -m graphify codex install
python -m graphify update .
```

Codex skill usage may use `$graphify .` after registration. In PowerShell, use the CLI form:

```powershell
graphify .
```

In this workspace, the verified fallback command is:

```powershell
python -m graphify update .
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

`graphify-out/` is ignored by git because it is generated local analysis output. Promote only intentional summaries, such as a reviewed root `GRAPH_REPORT.md`, if a report should be versioned.

## Safety Notes

- Graphify is optional and dev-only.
- Graphify must not change the deterministic risk engine or simulation execution boundary.
- Review upstream Graphify privacy and backend behavior before analyzing non-code assets or using headless extraction.
