# Freshdesk Local Exporter

A local desktop/web app for previewing Freshdesk API v2 ticket searches and exporting matching tickets. Ticket data goes directly between this machine and the configured Freshdesk account; API keys stay in backend process memory and are never written to exports, logs, or browser storage.

## What It Does

- Connects to Freshdesk with a domain and API key.
- Loads searchable ticket fields, including supported custom and lookup fields.
- Builds and validates Freshdesk search queries.
- Previews search results before export.
- Exports matching tickets as XLSX or AI-readable Markdown.
- Fetches ticket conversations separately so exports are not limited by Freshdesk `include=conversations` behavior.
- Splits large date-ranged exports to avoid Freshdesk's 300-result search ceiling where possible.

## Architecture

```text
React/Vite UI
  -> Desktop loopback server
  -> FastAPI backend on 127.0.0.1
  -> Freshdesk API v2
  -> local exports directory
```

The browser development workflow calls the backend directly through `VITE_API_BASE`. The desktop workflow serves the built UI and proxies `/api/*` through one local origin so the HTTP-only session cookie works consistently.

## Project Layout

```text
backend/app/       FastAPI service, Freshdesk client, query builder, export writer
backend/tests/     Backend unit tests
frontend/src/      React UI
scripts/           Desktop development and Windows build entrypoints
exports/           Local export output, created at runtime and ignored
```

## Run The App

The simplest local desktop path is kept in one place:

```powershell
.\scripts\devtest.ps1
```

That command builds and opens the portable WebView2 app.
From File Explorer, right-click `scripts\devtest.ps1` and choose **Run with PowerShell**.

## Build Windows EXE

The simple build path lives beside the test path:

```powershell
.\scripts\build.ps1
```

The build creates `frontend/release/Freshdesk Local Exporter-0.1.0-portable.exe`.
From File Explorer, right-click `scripts\build.ps1` and choose **Run with PowerShell**.
The output version comes from `frontend/package.json` by default; pass
`-Version <version>` when building a release from a matching Git tag. Pass
`-SkipSigning` when deliberately producing an unsigned build.

The build signs the final EXE when it finds a current-user code-signing
certificate named `Freshdesk Local Exporter Internal`. To choose a different
certificate from `Cert:\CurrentUser\My`, pass
`-SigningCertificateThumbprint <thumbprint>` or set
`FRESH_EXPORTER_SIGNING_THUMBPRINT` before running the build. If no matching
certificate is available, the build publishes an unsigned EXE and prints a
warning.

For binaries you plan to publish, build from a clean checkout on Windows and
keep the build inputs reviewable:

- Portable Python is pinned to `3.12.10` in `scripts/build.ps1`, and its bundled
  Python packages are pinned in `backend/windows-build-requirements.txt`.
- The WebView2 SDK package used to compile the host is pinned in
  `scripts/build.ps1`. The produced EXE still uses the Microsoft Edge WebView2
  Runtime installed on the user's machine instead of bundling a browser runtime.
- Frontend packages come from `frontend/package-lock.json`; the Windows build
  uses `npm ci` when it needs to install them.
- The build machine must provide Windows PowerShell, Node/npm compatible with
  the frontend lockfile, an installed Python that can run `pip`, and the .NET
  Framework C# compiler at the Windows framework path checked by the script.
- Public GitHub Release EXEs are unsigned and can trigger Windows SmartScreen
  or managed endpoint warnings. The local internal certificate path is for
  development and controlled internal trust only.
- Public Windows release automation is documented in
  [docs/releasing.md](docs/releasing.md).

## Browser Development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use any installed Python version that satisfies `requires-python >=3.12`.

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

Desktop development on Windows:

```powershell
.\scripts\devtest.ps1
```

## Backend API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Local readiness probe. |
| `POST` | `/api/connect` | Validates Freshdesk credentials and starts an in-memory session. |
| `GET` | `/api/connection` | Reports current connection state. |
| `GET` | `/api/fields` | Loads available filter fields. |
| `POST` | `/api/query` | Builds and validates a Freshdesk search query. |
| `POST` | `/api/preview` | Runs page 1 of a ticket search. |
| `POST` | `/api/export` | Writes XLSX or Markdown export files plus a manifest. |

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `FRONTEND_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS allowlist for browser development. |
| `EXPORT_DIR` | `./exports` | Directory for export files and manifests. |
| `SESSION_COOKIE_NAME` | `freshdesk_export_session` | HTTP-only cookie key for the local in-memory session. |
| `HOST` | `127.0.0.1` | Backend bind host used by the desktop launcher. |
| `PORT` | `8000` | Backend port used by the desktop launcher. |
| `LOG_LEVEL` | `warning` | Uvicorn log level for the desktop backend process. |

## Security

This project is designed for local use. Exports and manifests can contain
sensitive Freshdesk ticket data, contact details, conversations, account
domains, filter values, and search queries. Keep generated export files out of
public commits and review [SECURITY.md](SECURITY.md) before publishing builds or
sharing output.

## Implementation Notes

- API keys are held only in backend process memory. The session cookie stores an opaque ID, not credentials.
- Markdown exports render ticket descriptions and conversations as compact AI-readable text, while preserving non-empty fields not shown elsewhere as compact JSON. XLSX exports provide workbook sheets for tickets, conversations, and export metadata.
- Freshdesk search can cap accessible results at 300 for a single query. Large exports require a date range so the backend can split the search into smaller windows.
- Desktop mode serves the UI and API proxy from one loopback origin so the HTTP-only session cookie behaves consistently.

## Test

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm run build
```
