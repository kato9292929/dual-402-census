"""Unpaid HTTP prober. Plain httpx: no payment client, no signing, no keys.

One request per host. The catalog (endpoints_full.json) carries no HTTP
method or input schema, so every route is sent as GET first; only when GET is
answered with a "wrong method/shape" status (FALLBACK_STATUSES) is it retried
once as POST with the minimal JSON body "{}". Both statuses are recorded. Global concurrency 8; a host is only ever touched by one task, so its
requests are strictly sequential.
"""

import asyncio
import datetime as dt
import json
import os
import socket
import ssl
import time

import httpx

from census import parse as P

UA = "dual-402-census (+https://x402jp.com)"
TIMEOUT = 10.0  # per request, wall clock (asyncio.wait_for) and per phase (httpx)
CONCURRENCY = 8
BODY_CAP = 256 * 1024
FALLBACK_STATUSES = {400, 404, 405, 411, 415, 422}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


async def _send(client, method, url):
    kw = {"headers": {"user-agent": UA, "accept": "application/json, */*"}}
    if method == "POST":
        kw["content"] = b"{}"
        kw["headers"]["content-type"] = "application/json"
    t0 = time.monotonic()
    async with client.stream(method, url, **kw) as r:
        buf = bytearray()
        async for chunk in r.aiter_bytes():
            buf += chunk
            if len(buf) >= BODY_CAP:
                break
        return r, bytes(buf[:BODY_CAP]), round((time.monotonic() - t0) * 1000)


async def _error_kind(exc, host):
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError)):
        return "timeout"
    msg = str(exc)
    if isinstance(exc, ssl.SSLError) or "SSL" in msg or "CERTIFICATE" in msg.upper():
        return "tls"
    # Through the egress proxy a failed CONNECT surfaces as ProxyError 502 for
    # both DNS and TCP failures; disambiguate with a local resolve.
    name = host.split(":")[0]
    try:
        await asyncio.get_running_loop().getaddrinfo(name, 443)
    except socket.gaierror:
        return "dns"
    except Exception:
        pass
    return "connect" if isinstance(exc, (httpx.ConnectError, httpx.ProxyError)) else "other"


def record(target, r, body, ms, method, fallback):
    hdrs = r.headers
    x = P.parse_x402(hdrs.get_list("payment-required"), body.decode("utf-8", "replace"))
    m = P.parse_mpp(hdrs.get_list("www-authenticate"))
    label, wrap = P.classify(r.status_code, x, m)
    return {
        "status": r.status_code,
        "latency_ms": ms,
        "method_used": method,
        "post_fallback": fallback,
        "final_url": str(r.url),
        "content_type": hdrs.get("content-type"),
        "x402": x,
        "mpp": m,
        "other_payment_headers": P.other_payment_headers(list(hdrs.keys()), m["other_auth_schemes"]),
        "classification": label,
        "wrapper_estimate": wrap,
        "body_excerpt": body[:400].decode("utf-8", "replace") if label == P.UNKNOWN_402 else None,
    }


async def probe_one(client, sem, target):
    row = {k: target.get(k) for k in ("host", "url", "category", "own", "in_catalog", "rule")}
    method = (target.get("method") or "GET").upper()
    async with sem:
        row["measured_at"] = now()
        try:
            r, body, ms = await asyncio.wait_for(_send(client, method, target["url"]), TIMEOUT)
            fallback = False
            row["get_status"] = r.status_code if method == "GET" else None
            if method == "GET" and r.status_code in FALLBACK_STATUSES:
                r, body, ms = await asyncio.wait_for(_send(client, "POST", target["url"]), TIMEOUT)
                method, fallback = "POST", True
            row.update(record(target, r, body, ms, method, fallback))
        except Exception as e:  # network-level failure
            row.update({
                "status": None, "latency_ms": None, "method_used": method,
                "classification": P.ERROR, "wrapper_estimate": False,
                "error_kind": await _error_kind(e, target["host"]),
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            })
    return row


async def probe_all(targets, out_path, progress_every=500):
    sem = asyncio.Semaphore(CONCURRENCY)
    limits = httpx.Limits(max_connections=CONCURRENCY * 2, max_keepalive_connections=0)
    verify = os.environ.get("SSL_CERT_FILE") or True
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True, max_redirects=5,
                                 limits=limits, verify=verify) as client:
        tasks = [asyncio.create_task(probe_one(client, sem, t)) for t in targets]
        n = 0
        with open(out_path, "w") as f:
            for fut in asyncio.as_completed(tasks):
                row = await fut
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
                if progress_every and n % progress_every == 0:
                    f.flush()
                    print(f"{now()} {n}/{len(targets)}", flush=True)
    return n
