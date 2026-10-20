"""Build data/targets.jsonl: one representative route per host.

Rule (also in README):
  1. Host = lowercased netloc of the catalog URL (http/https only).
  2. Among the host's routes with a price amount > 0, take the cheapest by
     amount; ties -> the first in catalog order. Currency is ignored for the
     comparison (all are USD-denominated stablecoins/USD in the catalog).
  3. A host with no priced route -> its first route in catalog order.
  4. Own hosts (endpoint/jin/osd/rfq/probe .x402jp.com) are always included.
     If the host publishes /.well-known/x402.json, the same rule (cheapest
     priced, tie -> first) is applied to that document instead, skipping
     templated paths like /api/catalyst/{ticker} or /:ticker; otherwise the catalog rule,
     and "/" when the host is not in the catalog.

Usage: python scripts/build_targets.py /path/to/endpoint/data/endpoints_full.json.gz
"""

import gzip
import json
import pathlib
import re
import sys
import urllib.parse

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[1]
OWN = [f"{h}.x402jp.com" for h in ("endpoint", "jin", "osd", "rfq", "probe")]
UA = "dual-402-census (+https://x402jp.com)"


def host_of(url):
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    h = u.hostname.lower()
    if u.port and not ((u.scheme == "https" and u.port == 443) or (u.scheme == "http" and u.port == 80)):
        h = f"{h}:{u.port}"
    return h


def amount(e):
    p = e.get("price")
    if isinstance(p, dict) and isinstance(p.get("amount"), (int, float)) and p["amount"] > 0:
        return float(p["amount"])
    return None


def pick(routes):
    priced = [(amount(e), i, e) for i, e in enumerate(routes) if amount(e) is not None]
    if priced:
        a, _, e = min(priced, key=lambda t: (t[0], t[1]))
        return e, "cheapest_priced"
    return routes[0], "no_priced_route_first"


def price_usd(s):
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str) and s.strip().startswith("$"):
        try:
            return float(s.strip()[1:])
        except ValueError:
            return None
    return None


def own_discovery(host, outdir):
    """Cheapest priced non-templated route from the host's /.well-known/x402.json, or None."""
    url = f"https://{host}/.well-known/x402.json"
    try:
        r = httpx.get(url, headers={"user-agent": UA}, timeout=10, follow_redirects=True)
        doc = r.json() if r.status_code == 200 else None
    except Exception:
        doc = None
    if not isinstance(doc, dict):
        return None
    (outdir / f"{host}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    cands = []
    for i, ep in enumerate(doc.get("endpoints") or []):
        if not isinstance(ep, dict):
            continue
        res = ep.get("resource") or (doc.get("base_url", f"https://{host}").rstrip("/") + ep.get("path", ""))
        if "{" in res or re.search(r"/:[A-Za-z_]", res):
            continue
        p = price_usd(ep.get("price"))
        if p is None:
            for a in ep.get("accepts") or []:
                try:
                    p = int(a.get("amount")) / 1e6  # USDC base units (6 decimals)
                    break
                except (TypeError, ValueError):
                    pass
        if ep.get("free") is True or p is None or p <= 0:
            continue
        cands.append((p, i, res, ep.get("method", "GET")))
    if not cands:
        return None
    p, _, res, method = min(cands, key=lambda t: (t[0], t[1]))
    return {"url": res, "method": method, "price_usd": p}


def main(path):
    raw = json.load(gzip.open(path) if str(path).endswith(".gz") else open(path))
    eps = raw["endpoints"]
    by_host = {}
    for e in eps:
        h = host_of(e.get("url", ""))
        if h:
            by_host.setdefault(h, []).append(e)
    targets = []
    for h, routes in by_host.items():
        e, rule = pick(routes)
        targets.append({
            "host": h, "url": e["url"], "method": "GET", "rule": rule,
            "catalog_price": e.get("price"), "category": e.get("category"),
            "catalog_routes": len(routes), "own": False, "in_catalog": True,
        })
    disc_dir = ROOT / "data" / "own-discovery"
    disc_dir.mkdir(parents=True, exist_ok=True)
    idx = {t["host"]: t for t in targets}
    for h in OWN:
        t = idx.get(h)
        if t is None:
            t = {"host": h, "url": f"https://{h}/", "method": "GET", "rule": "own_not_in_catalog_root",
                 "catalog_price": None, "category": None, "catalog_routes": 0, "in_catalog": False}
            targets.append(t)
            idx[h] = t
        t["own"] = True
        d = own_discovery(h, disc_dir)
        if d:
            t["catalog_url"] = t["url"]
            t.update(url=d["url"], method=d["method"].upper(), rule="own_well_known_cheapest", own_price_usd=d["price_usd"])
    meta = {"snapshot_generated_at": raw.get("generated_at"), "catalog_count": raw.get("count"),
            "hosts": len(targets), "own_hosts": len(OWN),
            "own_hosts_in_catalog": sum(1 for h in OWN if idx[h]["in_catalog"])}
    with open(ROOT / "data" / "targets.jsonl", "w") as f:
        for t in targets:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    (ROOT / "data" / "targets.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
