"""Run the census: probe every host in data/targets.jsonl once, unpaid.

Usage: python scripts/probe.py [--limit N] [--hosts h1,h2]
Writes data/census-<UTCstamp>.jsonl and data/census-latest.txt (its name).
"""

import argparse
import asyncio
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from census.probe import probe_all, now  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--hosts")
    ap.add_argument("--out")
    a = ap.parse_args()
    targets = [json.loads(l) for l in open(ROOT / "data" / "targets.jsonl")]
    if a.hosts:
        want = set(a.hosts.split(","))
        targets = [t for t in targets if t["host"] in want]
    if a.limit:
        targets = targets[: a.limit]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = pathlib.Path(a.out) if a.out else ROOT / "data" / f"census-{stamp}.jsonl"
    started = now()
    n = asyncio.run(probe_all(targets, out))
    meta = {"file": out.name, "started_at": started, "finished_at": now(), "targets": len(targets), "rows": n}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2))
    if not a.out and not a.limit and not a.hosts:
        (ROOT / "data" / "census-latest.txt").write_text(out.name + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    main()
