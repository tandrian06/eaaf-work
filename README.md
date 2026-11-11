# EAAF Work

EAAF Work is the chat and document-search application for EAAF. It serves the Global, HR, IT, and Marketing spaces and connects to the [EAAF Core Gateway](https://github.com/tandrian06/eaaf) over HTTP.

## Run locally

Start EAAF Core using its Docker Compose instructions. From this repository in PowerShell with Python 3.14:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn eaaf_work.app:app --host 127.0.0.1 --port 8001
```

Open [EAAF Work](http://127.0.0.1:8001/) and enter the application key for the selected space from Core's local `.env`. Work uses `http://127.0.0.1:8000` by default. Set `EAAF_GATEWAY_URL` before starting Work to use another Gateway.

## Architecture

The browser loads the UI from Work. Work forwards model options and chat requests to Core on the same browser origin. The browser holds the application key in page memory. Work forwards the Authorization header to Core and does not persist it. Core remains responsible for application identity, model access, usage limits, audit, and department-scoped RAG during this first extraction increment.

The existing Core UI is still available for compatibility. Moving document retrieval and its authorization boundary into Work is a separate increment.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```
