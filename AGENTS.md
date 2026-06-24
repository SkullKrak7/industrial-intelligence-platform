# Agent Instructions

<!--
AGENTS.md is read by Claude Code, OpenAI Codex CLI, Cursor, Aider, Devin, Google Jules,
and most other AI coding tools. Keep it tool-agnostic: plain markdown, no special syntax.

CONSTRAINTS (from the open specification at agents.md):
- Each section: under 50 lines
- Total file: under 150 lines
- Closest file to the edited file wins over a parent-directory file

WHAT BELONGS HERE vs CLAUDE.md:
- AGENTS.md  → HOW the agent should think and behave (tool-agnostic, universal)
- CLAUDE.md  → WHAT the project is and its specific rules (Claude Code, project-specific)

Point CLAUDE.md at this file with "@AGENTS.md" on its first line.
-->

## Before writing a single line of code

1. Read `CLAUDE.md` in full — stack, version gotchas, rules, architecture.
2. Read every file you plan to touch. Understand the existing pattern before inventing one.
3. Check `pipeline/models.py` for canonical Pydantic schemas. Never duplicate them.
4. Check `tests/` to understand test patterns before writing new tests.
5. If the task spans more than 3 files or touches a shared abstraction: state your plan
   in 2–3 sentences and wait for approval before writing code.

## How to approach a task

**Diagnose before fixing.** Read the error. Read the code. Understand the root cause.
Python tracebacks point to the exact line — read the full stack before touching anything.

**Match the existing pattern.** Before adding an abstraction, check if one already exists.
Three similar lines of code is better than a premature helper function.

**Verify locally before declaring done.** Run `pytest pipeline/tests/` and (for dbt work) `dbt run --project-dir dbt/`.
If you cannot run it, say so explicitly — never claim a task is complete without it.

**For API changes.** Run the dev server and hit `/v1/predict` with a sample payload via curl or pytest — verify the response schema matches `PredictResponse` in `pipeline/models.py`.

**Report before acting on data.** When investigating a data issue: query, observe, report
findings. Do not mutate records unless the user explicitly instructs it.

## Hard limits — never do these without explicit instruction

- Do not run SQL mutations (UPDATE / DELETE / INSERT) or database migrations
- Do not push to remote, open pull requests, or merge branches
- Do not send emails, SMS, notifications, or call external webhooks
- Do not delete files that are not obviously temporary (build output, coverage reports)
- Do not commit changes unless the user explicitly says "commit this"
- Do not bypass the pre-push hook (`git push --no-verify`) for anything going to main
- Do not hardcode secrets, keys, or tokens — even in scripts or one-off files

## Quality bar — every change must clear this

- All existing tests green (`pytest pipeline/tests/`); new pure functions and validation logic get unit tests
- No unused imports, variables, or dead code left behind
- MLflow: every training run is tracked; models are loaded via alias, never file path
- dbt: all three model layers run clean (`dbt run`) before declaring work done
- Dagster assets must be idempotent — safe to retry without side effects
- Comments explain WHY, never WHAT — if the comment restates the code, delete it

## Secrets and security

The CI runs a secret-leak scan on every push. It flags:
- Variable assignments with literal string values: `KEY\s*=\s*["']`
- Raw JWT strings > 100 chars: `eyJ[A-Za-z0-9_-]{100,}`
- All source file types including `*.mjs` — scripts are not exempt

Always use `os.getenv("MY_SECRET")` or `os.environ["MY_SECRET"]`. Never assign a literal credential, even temporarily.

## Framework-specific gotchas

See `CLAUDE.md → Version-specific gotchas` for the full list. Key ones:

- **MLflow 2.x aliases**: Do not use `.transition_model_version_stage()` — stages are deprecated. Use `client.set_registered_model_alias()` instead.
- **dbt-duckdb**: `dbt-core` alone is not enough. Must install `dbt-duckdb`. Profile must target DuckDB, not Postgres.
- **FastAPI**: No `app.run()`. Serve with `uvicorn pipeline.api:app`. Pydantic v2 is the default — use `model.model_dump()` not `model.dict()`.
- **Dagster**: `@asset` outputs must be deterministic and idempotent. Re-running an asset must not duplicate MLflow runs or CSV rows.

The standing rule: **do not assume library behaviour matches training data.** When using any API that could have changed between versions, check the installed package source or changelog first.

## Common mistakes to check before calling a task done

- **Hardcoded file path?** Any path to `data/`, `dbt/`, or `outputs/` must come from config or env — not a string literal in the code.
- **Model loaded from file path?** The API must resolve `@champion` via `MlflowClient().get_model_version_by_alias()` and download the composite pkl via `mlflow.artifacts.download_artifacts()`. Loading directly from `model.pkl` on disk is only the build-time fallback.
- **Dagster asset not idempotent?** Check that re-running it won't create duplicate MLflow runs, duplicate CSV rows, or re-promote an already-promoted model version.
- **dbt run not verified?** Always run `dbt run --project-dir dbt/` and confirm clean output before declaring dbt work done.
- **Secret in source?** Any API key, MLflow tracking URI with credentials, or cloud storage key assigned inline is permanently in git history on push. Always use environment variables.
- **Pydantic v2 API?** Use `model.model_dump()` not `model.dict()`. Use `model_validator` not `validator`. Check the installed Pydantic version if uncertain.
- **Tests still green?** Run `pytest pipeline/tests/` after every change. The pipeline repo has existing tests that must not regress.

## Web research protocol

When the user asks to research a topic using web search, structure results across exactly these four segments — 5 sources each, 20 total:

1. **Top companies** — reputed large organisations
2. **Freelance / indie developers** — individual practitioner blogs, Substacks, Medium posts
3. **Fast-scaling startups** — companies that scaled rapidly and wrote about what worked
4. **Implementation docs** — official framework/library documentation

**Always include the current month and year in every query** (e.g. "June 2026") to get the most recent results — never omit the date or use a past year.

Run all four search queries in parallel. Synthesise the findings, then close with: **"What this means for this project"** — a concrete recommendation grounded in the research, not a summary of summaries.

## Meta-rule for maintaining this file

Only add a rule when you observe the same class of mistake **twice**.
Once = noise. Twice = pattern worth encoding.
One well-enforced specific rule beats ten vague guidelines.
