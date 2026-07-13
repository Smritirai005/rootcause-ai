"""
logs_tool.py

Reads REAL production log data from the Loghub HDFS dataset
(https://github.com/logpai/loghub) and exposes it as a queryable tool
for the investigation agent.

Loghub note: the full labeled anomaly_label.csv requires a Zenodo download
(not available via plain HTTP), so this module derives anomalies directly
from the raw log content using known HDFS error signatures (WARN/ERROR/
Exception lines around DataXceiver, PacketResponder, etc). This is a
label-proxy, not the official benchmark label set — worth being upfront
about that in your writeup.
"""

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_PATH = Path(__file__).parent.parent / "data" / "loghub" / "HDFS_2k.log"

# 081109 203615 148 INFO dfs.DataNode$PacketResponder: message...
LOG_LINE_RE = re.compile(
    r"^(?P<date>\d{6})\s+(?P<time>\d{6})\s+(?P<pid>\d+)\s+(?P<level>\w+)\s+"
    r"(?P<component>[\w\.\$]+):\s*(?P<message>.*)$"
)

ANOMALY_KEYWORDS = ("exception", "error", "fail", "terminating abnormally")


@dataclass
class LogEntry:
    timestamp: str
    pid: str
    level: str
    component: str
    message: str
    is_anomaly: bool

    def to_dict(self):
        return asdict(self)


def _parse_line(line: str) -> Optional[LogEntry]:
    line = line.strip()
    m = LOG_LINE_RE.match(line)
    if not m:
        return None
    d = m.groupdict()
    # 081109 -> 2008-11-09, 203615 -> 20:36:15
    ts = datetime.strptime(d["date"] + d["time"], "%y%m%d%H%M%S").isoformat()
    is_anomaly = any(k in d["message"].lower() for k in ANOMALY_KEYWORDS) or d["level"] in (
        "WARN",
        "ERROR",
    )
    return LogEntry(
        timestamp=ts,
        pid=d["pid"],
        level=d["level"],
        component=d["component"],
        message=d["message"],
        is_anomaly=is_anomaly,
    )


def load_all_logs() -> list[LogEntry]:
    entries = []
    with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            entry = _parse_line(line)
            if entry:
                entries.append(entry)
    return entries


def read_logs(
    keyword: Optional[str] = None,
    level: Optional[str] = None,
    only_anomalies: bool = False,
    limit: int = 50,
) -> list[dict]:
    """
    MCP-exposed tool: query the real HDFS log dataset.

    Args:
        keyword: substring filter on the log message (case-insensitive)
        level: exact log level filter, e.g. "WARN", "ERROR", "INFO"
        only_anomalies: if True, only return entries flagged as anomalies
        limit: max number of entries to return
    """
    entries = load_all_logs()

    if keyword:
        entries = [e for e in entries if keyword.lower() in e.message.lower()]
    if level:
        entries = [e for e in entries if e.level == level.upper()]
    if only_anomalies:
        entries = [e for e in entries if e.is_anomaly]

    return [e.to_dict() for e in entries[:limit]]


def get_metrics() -> dict:
    """
    MCP-exposed tool: derive simple aggregate metrics from the real log data
    (stand-in for a CloudWatch metrics call — same shape, real underlying data).
    """
    entries = load_all_logs()
    total = len(entries)
    anomalies = [e for e in entries if e.is_anomaly]
    by_level = {}
    for e in entries:
        by_level[e.level] = by_level.get(e.level, 0) + 1

    return {
        "total_log_lines": total,
        "anomaly_count": len(anomalies),
        "anomaly_rate_pct": round(100 * len(anomalies) / total, 2) if total else 0,
        "lines_by_level": by_level,
        "first_timestamp": entries[0].timestamp if entries else None,
        "last_timestamp": entries[-1].timestamp if entries else None,
    }


if __name__ == "__main__":
    # quick smoke test
    print("Total parsed lines:", len(load_all_logs()))
    print("Metrics:", get_metrics())
    print("Sample anomalies:")
    for e in read_logs(only_anomalies=True, limit=3):
        print(" -", e["timestamp"], e["level"], e["message"][:80])
