"""
github_tool.py

Pulls REAL commit history from a public GitHub repo via the GitHub REST API.
No auth required for public repos at low volume, but set GITHUB_TOKEN in
.env to raise your rate limit from 60/hr to 5000/hr.

Pick any repo you know well as REPO_OWNER/REPO_NAME below, or pass one in.
"""

import os
import requests
from datetime import datetime
from typing import Optional

GITHUB_API = "https://api.github.com"


def _headers():
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def read_github_commits(
    owner: str,
    repo: str,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    MCP-exposed tool: fetch real recent commits for a repo.

    Args:
        owner: repo owner, e.g. "tiangolo"
        repo: repo name, e.g. "fastapi"
        since: ISO8601 timestamp, only commits after this time
        until: ISO8601 timestamp, only commits before this time
        limit: max commits to return
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits"
    params = {"per_page": min(limit, 100)}
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    resp = requests.get(url, headers=_headers(), params=params, timeout=15)
    resp.raise_for_status()
    commits = resp.json()

    return [
        {
            "sha": c["sha"][:8],
            "author": (c.get("commit", {}).get("author") or {}).get("name"),
            "date": (c.get("commit", {}).get("author") or {}).get("date"),
            "message": c.get("commit", {}).get("message", "").split("\n")[0],
            "url": c.get("html_url"),
        }
        for c in commits[:limit]
    ]


def get_commit_files(owner: str, repo: str, sha: str) -> list[dict]:
    """
    MCP-exposed tool: get the files changed in a specific real commit.
    Useful once the investigation narrows to a suspect commit.
    """
    url = f"{GITHUB_API}/repos/{owner}/{repo}/commits/{sha}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return [
        {
            "filename": f["filename"],
            "status": f["status"],
            "additions": f["additions"],
            "deletions": f["deletions"],
            "patch_preview": (f.get("patch") or "")[:300],
        }
        for f in data.get("files", [])
    ]


if __name__ == "__main__":
    # smoke test against a real, active public repo
    commits = read_github_commits("tiangolo", "fastapi", limit=5)
    for c in commits:
        print(c["date"], c["sha"], "-", c["message"])
