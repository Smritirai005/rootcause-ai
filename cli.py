"""
cli.py — Week 1 deliverable: a working CLI that investigates an incident
end to end using real log data and real GitHub commits.

Usage:
    python cli.py "The payment API suddenly started returning 500 errors after today's deployment."
"""

import sys
from agents.pipeline import investigate
import json


def main():
    if len(sys.argv) < 2:
        query = input("Describe the incident: ")
    else:
        query = " ".join(sys.argv[1:])

    print(f"\n🔎 Investigating: {query}\n")
    result = investigate(query)

    print("─" * 60)
    print("PLAN")
    print("─" * 60)
    print(result["plan"])

    print("\n" + "─" * 60)
    print("EVIDENCE COLLECTED")
    print("─" * 60)
    m = result["evidence"]["metrics"]
    print(f"Log anomalies found: {m['anomaly_count']} / {m['total_log_lines']} lines ({m['anomaly_rate_pct']}%)")
    print(f"Log window: {m['first_timestamp']} → {m['last_timestamp']}")
    print(f"Recent commits checked: {len(result['evidence']['recent_commits'])}")

    print("\n" + "─" * 60)
    print("FINAL REPORT")
    print("─" * 60)
    print(json.dumps(result["report"], indent=2))


if __name__ == "__main__":
    main()
