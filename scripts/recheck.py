"""24-hour recheck: re-probe only hosts first classified 両対応 or MPPのみ and
report how many keep the same classification (A12).

Usage:
  python scripts/recheck.py --plan     # record the due time (first-run hosts' last measured_at + 24h)
  python scripts/recheck.py            # run (refuses before the due time unless --force)
Writes data/recheck-<UTCstamp>.jsonl, data/recheck-summary.json, then regenerates docs/results.md.
"""

import argparse
import asyncio
import collections
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from census import parse as P  # noqa: E402
from census.probe import probe_all, now  # noqa: E402
from scripts import aggregate  # noqa: E402

SUMMARY = ROOT / "data" / "recheck-summary.json"


def parse_ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cp = aggregate.census_path()
    first = [r for r in aggregate.load_jsonl(cp) if r["classification"] in (P.DUAL, P.MPP_ONLY)]
    if not first:
        due = None
    else:
        due = max(parse_ts(r["measured_at"]) for r in first) + dt.timedelta(hours=24)
    due_iso = due.isoformat(timespec="seconds").replace("+00:00", "Z") if due else None
    if a.plan:
        SUMMARY.write_text(json.dumps({"done": False, "census": cp.name, "hosts": len(first), "due_at": due_iso}, indent=2))
        print(SUMMARY.read_text())
        return
    if due and dt.datetime.now(dt.timezone.utc) < due and not a.force:
        sys.exit(f"too early: due at {due_iso}")
    targets_by_host = {json.loads(l)["host"]: json.loads(l) for l in open(ROOT / "data" / "targets.jsonl")}
    targets = [targets_by_host[r["host"]] for r in first]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ROOT / "data" / f"recheck-{stamp}.jsonl"
    started = now()
    asyncio.run(probe_all(targets, out, progress_every=0))
    second = {r["host"]: r for r in aggregate.load_jsonl(out)}
    trans = collections.Counter()
    matched = 0
    for r in first:
        c2 = second.get(r["host"], {}).get("classification", "未記録")
        trans[f"{r['classification']}→{c2}"] += 1
        matched += c2 == r["classification"]
    total = len(first)
    summary = {
        "done": True, "census": cp.name, "file": out.name, "due_at": due_iso,
        "started_at": started, "finished_at": now(), "total": total, "matched": matched,
        "rate_pct": round(100 * matched / total, 1) if total else None,
        "transitions": dict(trans),
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    aggregate.main()


if __name__ == "__main__":
    main()
