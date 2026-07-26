"""
rag/ingest.py

Downloads REAL documentation pages (raw markdown, unmodified) from two
public GitHub repos:
  - FastAPI docs   (tiangolo/fastapi)
  - Docker docs     (docker/docs)

These two were picked because they're the doc sources most relevant to
the kind of incidents this project investigates (API errors, DB connection
issues, networking/container problems), and because both projects happen
to host their docs as plain markdown in a public repo — so we can pull
real content over HTTP with zero cost and zero scraping fragility.

Run once: python rag/ingest.py
"""

import os
import requests

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "docs")

FASTAPI_BASE = "https://raw.githubusercontent.com/tiangolo/fastapi/master/docs/en/docs"
DOCKER_BASE = "https://raw.githubusercontent.com/docker/docs/main/content/manuals/engine"

# Curated by hand (not auto-listed) because the GitHub API's unauthenticated
# rate limit is too easily exhausted for a directory listing call. If you
# have a GITHUB_TOKEN, feel free to swap this for a dynamic listing later.
SOURCES = {
    "fastapi": [
        "tutorial/handling-errors.md",
        "tutorial/sql-databases.md",
        "tutorial/background-tasks.md",
        "tutorial/cors.md",
        "tutorial/middleware.md",
        "tutorial/dependencies/index.md",
        "tutorial/security/index.md",
        "advanced/middleware.md",
    ],
    "docker": [
        "network/_index.md",
        "storage/volumes.md",
        "containers/resource_constraints.md",
        "containers/multi-service_container.md",
    ],
}


def fetch(base_url: str, path: str) -> str | None:
    url = f"{base_url}/{path}"
    resp = requests.get(url, timeout=15)
    if resp.status_code != 200:
        print(f"  ✗ {url} -> {resp.status_code}")
        return None
    return resp.text


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    total = 0

    for source_name, paths in SOURCES.items():
        base_url = FASTAPI_BASE if source_name == "fastapi" else DOCKER_BASE
        source_dir = os.path.join(OUT_DIR, source_name)
        os.makedirs(source_dir, exist_ok=True)

        print(f"\nFetching {source_name} docs...")
        for path in paths:
            content = fetch(base_url, path)
            if content is None:
                continue
            filename = path.replace("/", "__")
            out_path = os.path.join(source_dir, filename)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  ✓ {path} ({len(content)} chars)")
            total += 1

    print(f"\nDone. {total} real doc pages saved to {OUT_DIR}")


if __name__ == "__main__":
    main()