"""
agents/pipeline.py  (Week 2)

Same 3-agent LangGraph shape as Week 1, but the Investigator node now
calls tools THROUGH the MCP server (mcp_server.py) via an MCP client
session over stdio, instead of importing the tool functions directly.
Also adds a 4th tool: search_docs (RAG over real FastAPI + Docker docs).

LangSmith tracing: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY
in .env and every node run below is automatically traced — no code
changes needed beyond those env vars, LangGraph picks them up.

Run: python cli.py "The payment API is failing after last deploy"
"""

import os
import sys
import json
import asyncio
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, END
from groq import Groq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

MODEL_NAME = "llama-3.3-70b-versatile"
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MCP_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "..", "mcp_server.py")],
)


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
        "report, decide what evidence to gather. Available MCP tools: "
        "read_logs, get_metrics, read_github_commits, search_docs. "
        "Respond in 2-3 short sentences describing your investigation plan."
    )
    plan = _llm(system, state["user_query"])
    return {**state, "plan": plan}


# ---------- Node 2: Investigator (now calls tools via MCP) ----------
async def _call_mcp_tools(user_query: str) -> dict:
    async with stdio_client(MCP_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            anomalies_res = await session.call_tool(
                "read_logs", {"only_anomalies": True, "limit": 10}
            )
            metrics_res = await session.call_tool("get_metrics", {})
            commits_res = await session.call_tool(
                "read_github_commits", {"owner": "tiangolo", "repo": "fastapi", "limit": 5}
            )
            # RAG: search docs using keywords pulled from the user's query
            docs_res = await session.call_tool(
                "search_docs", {"query": user_query, "top_k": 3}
            )

            def _extract(res):
                return json.loads(res.content[0].text)

            return {
                "log_anomalies": _extract(anomalies_res),
                "metrics": _extract(metrics_res),
                "recent_commits": _extract(commits_res),
                "relevant_docs": _extract(docs_res),
            }


def investigator_node(state: InvestigationState) -> InvestigationState:
    evidence = asyncio.run(_call_mcp_tools(state["user_query"]))
    return {**state, "evidence": evidence}


# ---------- Node 3: Recommendation ----------
def recommendation_node(state: InvestigationState) -> InvestigationState:
    system = (
        "You are a senior SRE writing a root cause analysis. You will be given "
        "real evidence: log anomalies, metrics, recent commits, and relevant "
        "documentation snippets retrieved via RAG. "
        "Rules: evidence first, conclusion second. Never state a root cause "
        "that isn't directly supported by the evidence provided. If the docs "
        "suggest a known fix pattern, reference it. "
        "Respond ONLY in this JSON shape: "
        '{"root_cause": str, "confidence": "low"|"medium"|"high", '
        '"suggested_fix": str, "evidence_cited": [str], "docs_referenced": [str]}'
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
        report = {"root_cause": raw, "confidence": "unknown", "suggested_fix": "", "evidence_cited": [], "docs_referenced": []}

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
    print(f"- {result['evidence']['metrics']['anomaly_count']} anomalies found")
    print(f"- {len(result['evidence']['recent_commits'])} recent commits checked")
    print(f"- {len(result['evidence']['relevant_docs'])} relevant doc chunks retrieved via RAG")

    print("\n=== FINAL REPORT ===")
    print(json.dumps(result["report"], indent=2))