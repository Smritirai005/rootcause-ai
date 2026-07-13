"""
pipeline.py

The 3-agent LangGraph pipeline for RootCause AI.

Planner Agent      -> decides what evidence is needed
Investigator Agent -> calls tools (logs, github, metrics) to gather evidence
Recommendation Agent -> produces root cause + confidence + fix, evidence-first

Uses Groq's free tier (llama-3.3-70b-versatile) by default. Swap MODEL_NAME
or the client if you want to point this at Gemini instead.

Run: python agents/pipeline.py "The payment API is failing after last deploy"
"""

import os
import sys
import json
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END
from groq import Groq

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from tools.logs_tool import read_logs, get_metrics
from tools.github_tool import read_github_commits

MODEL_NAME = "llama-3.3-70b-versatile"
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


class InvestigationState(TypedDict):
    user_query: str
    plan: Optional[str]
    evidence: Optional[dict]
    report: Optional[dict]


def _llm(system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content


# ---------- Node 1: Planner ----------
def planner_node(state: InvestigationState) -> InvestigationState:
    system = (
        "You are an incident investigation planner. Given a user's incident "
        "report, decide what evidence to gather. Available tools: "
        "read_logs(keyword, level, only_anomalies), get_metrics(), "
        "read_github_commits(owner, repo). "
        "Respond in 2-3 short sentences describing your investigation plan."
    )
    plan = _llm(system, state["user_query"])
    return {**state, "plan": plan}


# ---------- Node 2: Investigator ----------
def investigator_node(state: InvestigationState) -> InvestigationState:
    # deterministic tool calls for the MVP — the planner's text guides
    # *what* we look for, but tool invocation itself is explicit and
    # auditable rather than left to free-form agent tool selection.
    anomalies = read_logs(only_anomalies=True, limit=10)
    metrics = get_metrics()

    commits = []
    try:
        commits = read_github_commits("tiangolo", "fastapi", limit=5)
    except Exception as e:
        commits = [{"error": f"github fetch failed: {e}"}]

    evidence = {
        "log_anomalies": anomalies,
        "metrics": metrics,
        "recent_commits": commits,
    }
    return {**state, "evidence": evidence}


# ---------- Node 3: Recommendation ----------
def recommendation_node(state: InvestigationState) -> InvestigationState:
    system = (
        "You are a senior SRE writing a root cause analysis. You will be given "
        "real evidence: log anomalies, metrics, and recent commits. "
        "Rules: evidence first, conclusion second. Never state a root cause "
        "that isn't directly supported by the evidence provided. "
        "Respond ONLY in this JSON shape: "
        '{"root_cause": str, "confidence": "low"|"medium"|"high", '
        '"suggested_fix": str, "evidence_cited": [str]}'
    )
    user = (
        f"User report: {state['user_query']}\n\n"
        f"Evidence:\n{json.dumps(state['evidence'], indent=2, default=str)}"
    )
    raw = _llm(system, user)

    try:
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        report = json.loads(cleaned)
    except Exception:
        report = {"root_cause": raw, "confidence": "unknown", "suggested_fix": "", "evidence_cited": []}

    return {**state, "report": report}


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("planner", planner_node)
    graph.add_node("investigator", investigator_node)
    graph.add_node("recommendation", recommendation_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "investigator")
    graph.add_edge("investigator", "recommendation")
    graph.add_edge("recommendation", END)

    return graph.compile()


def investigate(user_query: str) -> dict:
    app = build_graph()
    result = app.invoke({"user_query": user_query, "plan": None, "evidence": None, "report": None})
    return result


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "The payment API suddenly started returning 500 errors after today's deployment."
    result = investigate(query)

    print("\n=== PLAN ===")
    print(result["plan"])

    print("\n=== EVIDENCE (summary) ===")
    print(f"- {result['evidence']['metrics']['anomaly_count']} anomalies found "
          f"({result['evidence']['metrics']['anomaly_rate_pct']}% of {result['evidence']['metrics']['total_log_lines']} log lines)")
    print(f"- {len(result['evidence']['recent_commits'])} recent commits checked")

    print("\n=== FINAL REPORT ===")
    print(json.dumps(result["report"], indent=2))
