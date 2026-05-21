# AGENTS.md

This file applies to the repository root and all descendants.

## Repository Context

Freshdesk Local Exporter is a local-first desktop and browser app for previewing
Freshdesk ticket searches and exporting the matching records.

- `backend/app/` contains the FastAPI service, Freshdesk client, query builder,
  field normalization, export discovery, and XLSX/Markdown writers.
- `backend/tests/` contains focused pytest coverage for backend behavior.
- `frontend/src/` contains the React/Vite workflow UI for connect, filter,
  preview, and export steps.
- `scripts/` contains the PowerShell and WebView2 Windows build/dev entrypoints.

The security boundary matters here: Freshdesk API keys stay in backend process
memory, while exports and manifests can contain customer ticket data.

## Discovery

Start with `README.md`, `SECURITY.md`, and the nearest implementation and tests
for the requested change. Prefer targeted reads before broad repository scans.

Skip generated, local, and dependency trees during normal discovery:
`exports/`, `logs/`, `local-data/`, `node_modules/`, `frontend/dist/`,
`frontend/release/`, `backend/runtime/`, `backend/runtime-fast/`,
`backend/build/`, `backend/dist/`, virtual environments, and cache folders.
Read or modify those only when the task is specifically about their output.

## Implementation Guidance

- Keep changes scoped to the requested behavior and reuse the existing split
  between backend contracts, Freshdesk behavior, and frontend workflow state.
- Treat `backend/app/schemas.py` and `frontend/src/types.ts` as the API contract
  pair when request or response shapes change.
- Preserve the local-session design. Browser development may use
  `VITE_API_BASE`; the desktop path relies on one loopback origin and an
  HTTP-only session cookie.
- Keep Freshdesk constraints visible in related changes: wrapped search queries
  are limited to 512 characters, open-ended `is not` filters may be applied
  after search, searches can hit the 300-result cap, date-window splitting is
  used to avoid silent truncation where possible, rate-limit context is surfaced,
  and ticket conversations are fetched separately for export.
- Do not commit credentials, real `.env` files, exported ticket data, manifests,
  logs, or local runtime/build outputs.

## Backend Conventions

- The backend targets Python 3.12+ with FastAPI, httpx, and Pydantic.
- Follow the existing Python style: explicit types, small helpers, concise
  docstrings where they add context, and lines near the configured 100-character
  Ruff limit.
- Keep Freshdesk clients closed on route and export paths, and preserve rate
  limit/error context when changing API calls.
- Add or update focused tests in `backend/tests/` when changing field
  normalization, query generation, post-filtering, export discovery, export
  writers, Freshdesk request behavior, or Windows/date helpers.

## Frontend Conventions

- The frontend is React 19 + TypeScript + Vite with shared CSS in
  `frontend/src/styles.css` and Lucide icons.
- Reuse the existing step-based workflow, request wrapper, screen components,
  and CSS vocabulary before introducing a new pattern.
- Keep backend/frontend changes together when a filter shape, warning, export
  result, or connection behavior crosses the API boundary.

## Git Workflow

- Before starting feature work, create a focused branch from the current main
  branch instead of editing directly on `main`.
- Keep commits scoped to the approved change and do not include unrelated local
  work.
- Commit, merge to `main`, and push only when the user says the change is ready
  for mainline publication.

## Verification

Use the smallest relevant check first, then broaden checks when the change spans
multiple layers.

- Backend work: from `backend/`, run `.\.venv\Scripts\python.exe -m pytest`
  when the repository virtual environment exists. Otherwise use a Python 3.12+
  environment with `pip install -e ".[dev]"` and run `python -m pytest`.
- Frontend work: from `frontend/`, run `npm run build`. This is the current
  TypeScript/build validation path.
- Desktop packaging or WebView2 launcher work: use `.\scripts\build.ps1`.
  Use `.\scripts\devtest.ps1 -SmokeTest` when an executable smoke check is
  relevant.
- Documentation-only work usually needs a careful diff review unless it changes
  commands, security assumptions, or build instructions that should be checked.

Report any skipped check and the reason.

## AGENTS.md Maintenance

Keep future edits concrete and repository-specific. Prefer setup facts, local
constraints, and verification commands that apply across this repository. Add a
nested `AGENTS.md` or `AGENTS.override.md` near specialized work only when that
subtree needs different guidance.
