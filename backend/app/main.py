"""
FastAPI entrypoint.
Location: app/main.py

Run with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import documents

app = FastAPI(
    title="CUAD Contract Classifier",
    docs_url=None,
    redoc_url=None,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = PROJECT_ROOT / "backend" / "static"

# Allow the React (Vite) dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
def api_docs() -> str:
    """Serve a dependency-free API documentation page."""
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CUAD Contract Classifier API</title>
    <style>
      body { font: 16px system-ui, sans-serif; max-width: 960px; margin: 40px auto; padding: 0 20px; color: #1b2430; }
      h1 { margin-bottom: 6px; } .muted { color: #5a6472; }
      section { border: 1px solid #d8d4cb; border-radius: 6px; margin: 16px 0; padding: 16px; }
      code, pre { background: #f4f2ee; border-radius: 4px; padding: 3px 6px; }
      pre { padding: 12px; overflow-x: auto; } a { color: #2f6f5e; }
    </style>
  </head>
  <body>
    <h1>CUAD Contract Classifier API</h1>
    <p class="muted">Interactive dependencies are not required. OpenAPI JSON: <a href="/openapi.json">/openapi.json</a></p>
    <div id="content"><p>Loading endpoints...</p></div>
    <script>
      const content = document.getElementById('content');
      fetch('/openapi.json').then(r => r.json()).then(spec => {
        content.innerHTML = Object.entries(spec.paths).map(([path, methods]) =>
          `<section><h2><code>${path}</code></h2>${Object.entries(methods).map(([method, operation]) =>
            `<p><strong>${method.toUpperCase()}</strong> ${operation.summary || operation.description || ''}</p>`
          ).join('')}</section>`
        ).join('');
      }).catch(error => {
        content.innerHTML = '<p>Unable to load the OpenAPI specification: ' + error.message + '</p>';
      });
    </script>
  </body>
</html>"""


app.include_router(documents.router)

if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST_DIR, html=True), name="frontend")
