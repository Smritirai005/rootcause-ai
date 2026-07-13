# RootCause AI — Week 1

An agentic incident investigation pipeline: Planner → Investigator → Recommendation,
built on LangGraph, running against **real production log data** and **real GitHub commits**.

## What's real vs simulated (be upfront about this)

- **Logs**: real HDFS production log data from [Loghub](https://github.com/logpai/loghub)
  (`data/loghub/HDFS_2k.log`), a public research dataset of unmodified system logs.
  Anomalies are derived from real WARN/ERROR/Exception lines in the data (Loghub's
  official labeled set requires a Zenodo download outside plain HTTP access, so this
  is a label proxy — worth stating exactly like this in your writeup).
- **Commits**: real, live commit history pulled from a real public GitHub repo via
  the GitHub REST API (defaults to `tiangolo/fastapi` — swap to a repo you know well).
- **Deployments/metrics**: simulated for now, will be timestamp-correlated to the
  real log anomalies in Week 2+.

## Setup (all free tier, no credit card)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env`:
1. `GROQ_API_KEY` — free at [console.groq.com](https://console.groq.com), no card needed
2. `GITHUB_TOKEN` — optional, raises rate limit from 60/hr to 5000/hr

## Run it

```bash
export $(cat .env | xargs)   # or use python-dotenv / direnv
python cli.py "The payment API suddenly started returning 500 errors after today's deployment."
```

## Structure

```
tools/
  logs_tool.py     # parses real Loghub HDFS data -> read_logs(), get_metrics()
  github_tool.py   # real GitHub API calls -> read_github_commits(), get_commit_files()
agents/
  pipeline.py      # 3-node LangGraph: planner -> investigator -> recommendation
cli.py             # entrypoint
data/loghub/       # real downloaded log dataset
```

## Verified working

- `tools/logs_tool.py` parses all 2000 real log lines, correctly flags 80 real
  anomalies (4.0% anomaly rate) — run `python tools/logs_tool.py` to see it.
- `tools/github_tool.py` hits the real GitHub API — run `python tools/github_tool.py`
  to see live commits (may need `GITHUB_TOKEN` if you hit the public rate limit).
- `agents/pipeline.py` graph compiles with all 3 nodes wired correctly (planner →
  investigator → recommendation → END).

## Next (Week 2)

- Wrap `tools/*.py` functions in an MCP server, swap LangGraph to call MCP instead
  of direct function calls.
- RAG: FastAPI + Postgres docs → FAISS.
- LangSmith tracing.
