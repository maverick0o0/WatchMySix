"""WatchMySix backend API server."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

WATCHMYSIX_WORDLIST_DIR = Path(
    os.environ.get("WATCHMYSIX_WORDLIST_DIR", "/opt/watchmysix/wordlists")
)
WATCHMYSIX_RESOLVER_DIR = Path(
    os.environ.get("WATCHMYSIX_RESOLVER_DIR", "/opt/watchmysix/resolvers")
)

app = FastAPI(title="WatchMySix API", version="1.0.0")


@app.get("/api/health")
def health() -> JSONResponse:
    """Report API status and presence of key tool directories."""
    status = {
        "status": "ok",
        "wordlist_dir": str(WATCHMYSIX_WORDLIST_DIR),
        "resolver_dir": str(WATCHMYSIX_RESOLVER_DIR),
        "go_binaries": sorted({"subfinder", "httpx", "puredns"}),
    }
    return JSONResponse(status)


@app.get("/api/wordlists")
def list_wordlists() -> JSONResponse:
    """Return a list of discovered wordlist files."""
    if not WATCHMYSIX_WORDLIST_DIR.exists():
        raise HTTPException(status_code=500, detail="Wordlist directory is missing")

    files: List[str] = [
        str(path.relative_to(WATCHMYSIX_WORDLIST_DIR))
        for path in WATCHMYSIX_WORDLIST_DIR.rglob("*")
        if path.is_file()
    ]
    return JSONResponse({"wordlists": files})


@app.get("/api/resolvers")
def list_resolvers() -> JSONResponse:
    """Return resolver files bundled with the toolkit."""
    if not WATCHMYSIX_RESOLVER_DIR.exists():
        raise HTTPException(status_code=500, detail="Resolver directory is missing")

    files: List[str] = [
        str(path.relative_to(WATCHMYSIX_RESOLVER_DIR))
        for path in WATCHMYSIX_RESOLVER_DIR.rglob("*")
        if path.is_file()
    ]
    return JSONResponse({"resolvers": files})
