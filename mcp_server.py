"""
mcp_server.py

A real MCP server exposing RootCause AI's tools:
  - read_logs
  - get_metrics
  - read_github_commits
  - search_docs

This is intentionally a single, thin, local server — not a distributed
system. The point of this file is to prove the agent talks to tools
*through the MCP protocol* rather than calling Python functions directly,
which is what the "MCP" line item on your JD checklist actually means.

Run standalone (for testing): python mcp_server.py
The LangGraph pipeline connects to this over stdio — see agents/pipeline.py
"""

import sys
import os
import json

sys.path.append(os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
from tools.logs_tool import read_logs as _read_logs, get_metrics as _get_metrics
from tools.github_tool import read_github_commits as _read_github_commits
from rag.search import search_docs as _search_docs

mcp = FastMCP("rootcause-ai")


@mcp.tool()
def read_logs(keyword: str = "", level: str = "", only_anomalies: bool = False, limit: int = 20) -> str:
    """Query the real HDFS production log dataset.
    keyword: substring filter on log message.
    level: log level filter (INFO/WARN/ERROR).
    only_anomalies: only return entries flagged as anomalies.
    limit: max entries to return.
    """
    results = _read_logs(
        keyword=keyword or None,
        level=level or None,
        only_anomalies=only_anomalies,
        limit=limit,
    )
    return json.dumps(results, default=str)


@mcp.tool()
def get_metrics() -> str:
    """Get aggregate metrics derived from the real log dataset
    (anomaly count/rate, lines by level, time window)."""
    return json.dumps(_get_metrics(), default=str)


@mcp.tool()
def read_github_commits(owner: str, repo: str, limit: int = 10) -> str:
    """Get real recent commits for a GitHub repo.
    owner: repo owner, e.g. 'tiangolo'.
    repo: repo name, e.g. 'fastapi'.
    limit: max commits to return.
    """
    results = _read_github_commits(owner, repo, limit=limit)
    return json.dumps(results, default=str)


@mcp.tool()
def search_docs(query: str, top_k: int = 3) -> str:
    """Semantic search over real indexed documentation (FastAPI + Docker docs).
    query: natural language question, e.g. 'database connection refused'.
    top_k: number of relevant chunks to return.
    """
    results = _search_docs(query, top_k=top_k)
    return json.dumps(results, default=str)


if __name__ == "__main__":
    mcp.run(transport="stdio")