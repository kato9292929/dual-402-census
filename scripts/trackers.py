"""Record x402scan / MPPscan "past 30 days" headline numbers from the public
pages, with fetch time and a screenshot in docs/screens/.

Values are read from the rendered page text exactly as displayed (e.g. "$1.23M").
Anything that cannot be read is written as 「取得できず」 — never estimated.

Usage: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python scripts/trackers.py
Writes data/trackers-<UTCstamp>.json and data/trackers-latest.json.
"""

import datetime as dt
import json
import pathlib
import re

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
NA = "取得できず"
NUM = r"(\$?[0-9][0-9.,]*\s?[KMB]?)"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def grab(text, label):
    m = re.search(rf"\n{label}\s*\n\s*{NUM}\s*\n", text)
    return m.group(1).strip() if m else NA


def x402scan(page, stamp):
    url = "https://www.x402scan.com/"
    out = {"site": "x402scan", "url": url, "fetched_at": None, "period_label": NA,
           "volume": NA, "transactions": NA, "buyers": NA, "buyers_label": "Buyers", "screenshot": None, "note": None}
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)
        out["fetched_at"] = now()
        text = page.inner_text("body")
        i = text.find("Overall Stats")
        seg = text[i:i + 800] if i >= 0 else ""
        if "Past 30 Days" in seg:
            out["period_label"] = "Past 30 Days"
            out["volume"] = grab(seg, "Volume")
            out["transactions"] = grab(seg, "Transactions")
            out["buyers"] = grab(seg, "Buyers")
        else:
            out["note"] = "Overall Stats の期間が「Past 30 Days」と確認できなかったため値を採らず"
        shot = ROOT / "docs" / "screens" / f"x402scan-{stamp}.png"
        page.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": 1400, "height": 1000})
        out["screenshot"] = str(shot.relative_to(ROOT))
    except Exception as e:
        out["note"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


SELECTED_JS = "e => !!e.parentElement.querySelector('.bg-primary')"


def _mpp_button(page, label, group):
    # The page has two "All" buttons: [0] = server scope (Featured/All),
    # [1] = time range (24h/7d/15d/30d/All).
    loc = page.locator("button", has_text=re.compile(rf"^{label}$"))
    return loc.nth(group) if label == "All" else loc.first


def mppscan(page, stamp, scope):
    """scope: "All" (all servers — the A11 value) or "Featured"."""
    url = "https://www.mppscan.com/"
    out = {"site": "MPPscan", "url": url, "scope": scope, "fetched_at": None, "period_label": NA,
           "volume": NA, "transactions": NA, "buyers": NA, "buyers_label": "Agents", "screenshot": None, "note": None}
    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        scope_btn = _mpp_button(page, scope, 0)
        range_btn = _mpp_button(page, "30d", 1)
        scope_btn.click()
        page.wait_for_timeout(1500)
        range_btn.click()
        page.wait_for_timeout(5000)
        page.wait_for_load_state("networkidle")
        out["fetched_at"] = now()
        ok_scope = scope_btn.evaluate(SELECTED_JS)
        ok_range = range_btn.evaluate(SELECTED_JS)
        if ok_scope and ok_range:
            out["period_label"] = "30d"
            text = page.inner_text("body")
            i = text.find("Usage")
            seg = text[i:i + 600] if i >= 0 else text
            out["volume"] = grab(seg, "Volume")
            out["transactions"] = grab(seg, "Transactions")
            out["buyers"] = grab(seg, "Agents")
            out["servers"] = grab(seg, "Servers")
        else:
            out["note"] = f"選択状態を確認できず値を採らず (scope={ok_scope}, 30d={ok_range})"
        shot = ROOT / "docs" / "screens" / f"mppscan-30d-{scope.lower()}-{stamp}.png"
        page.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": 1400, "height": 1000})
        out["screenshot"] = str(shot.relative_to(ROOT))
    except Exception as e:
        out["note"] = f"{type(e).__name__}: {str(e)[:200]}"
    return out


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (ROOT / "docs" / "screens").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1400, "height": 1000}, user_agent=None)
        res = {"x402scan": x402scan(ctx.new_page(), stamp),
               "mppscan": mppscan(ctx.new_page(), stamp, "All"),
               "mppscan_featured": mppscan(ctx.new_page(), stamp, "Featured")}
        b.close()
    js = json.dumps(res, ensure_ascii=False, indent=2)
    (ROOT / "data" / f"trackers-{stamp}.json").write_text(js)
    (ROOT / "data" / "trackers-latest.json").write_text(js)
    print(js)


if __name__ == "__main__":
    main()
