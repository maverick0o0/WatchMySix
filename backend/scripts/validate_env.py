"""Validate that required directories and binaries exist before startup."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

REQUIRED_BINARIES = [
    "subfinder",
    "httpx",
    "puredns",
]

REQUIRED_DIRECTORIES = [
    Path(os.environ.get("WATCHMYSIX_WORDLIST_DIR", "/opt/watchmysix/wordlists")),
    Path(os.environ.get("WATCHMYSIX_RESOLVER_DIR", "/opt/watchmysix/resolvers")),
]


def main() -> None:
    missing_bins = [binary for binary in REQUIRED_BINARIES if shutil.which(binary) is None]
    missing_dirs = [directory for directory in REQUIRED_DIRECTORIES if not directory.exists()]

    if missing_bins or missing_dirs:
        errors = []
        if missing_bins:
            errors.append(f"Missing binaries: {', '.join(missing_bins)}")
        if missing_dirs:
            errors.append(
                "Missing directories: "
                + ", ".join(str(directory) for directory in missing_dirs)
            )
        raise SystemExit("; ".join(errors))

    print("Environment validation passed.")


if __name__ == "__main__":
    main()
