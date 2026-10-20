"""Aggregate a census JSONL (+ trackers, + recheck) into docs/results.md (A1–A13).

Usage: python scripts/aggregate.py [data/census-XXXX.jsonl]
Defaults to the file named in data/census-latest.txt.
"""

import collections
import datetime as dt
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from census import parse as P  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))
NA = "取得できず"


def load_jsonl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def both_tz(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return f"{t.strftime('%Y-%m-%d %H:%M:%S')} UTC / {t.astimezone(JST).strftime('%Y-%m-%d %H:%M:%S')} JST"


def census_path(arg=None):
    if arg:
        return pathlib.Path(arg)
    return ROOT / "data" / (ROOT / "data" / "census-latest.txt").read_text().strip()


def status_bucket(r):
    if r["classification"] == P.ERROR:
        return f"エラー:{r.get('error_kind') or 'other'}"
    s = r["status"]
    return f"HTTP {s // 100}xx" if s not in (200, 404, 403, 401, 405, 429, 500, 502, 503) else f"HTTP {s}"


def tracker_line(t):
    if not t:
        return f"取引額 {NA} / 件数 {NA} / 買い手数 {NA}"
    s = (f"取引額 {t['volume']} / 件数 {t['transactions']} / 買い手数 {t['buyers']}"
         f"（画面ラベル: {t['buyers_label']}） / 期間 {t['period_label']} / 取得日時 "
         f"{both_tz(t['fetched_at']) if t.get('fetched_at') else NA}")
    if t.get("screenshot"):
        s += f" / スクリーンショット `{t['screenshot']}`"
    if t.get("note"):
        s += f" / 注記: {t['note']}"
    return s


def main(arg=None):
    cp = census_path(arg)
    rows = load_jsonl(cp)
    meta = json.loads(cp.with_suffix(".meta.json").read_text())
    tmeta = json.loads((ROOT / "data" / "targets.meta.json").read_text())
    by = collections.Counter(r["classification"] for r in rows)
    n402 = sum(1 for r in rows if r.get("status") == 402)
    dual = [r for r in rows if r["classification"] == P.DUAL]
    mpp_only = [r for r in rows if r["classification"] == P.MPP_ONLY]
    wrap = sum(1 for r in dual if r.get("wrapper_estimate"))

    nonpay = collections.Counter(status_bucket(r) for r in rows if r["classification"] in (P.NOT_402, P.ERROR))

    meth_ch = collections.Counter()
    meth_host = collections.Counter()
    intent_ch = collections.Counter()
    other_raw = collections.Counter()
    for r in dual + mpp_only:
        ms = set()
        for c in r["mpp"]["challenges"]:
            meth_ch[c["method_bucket"]] += 1
            intent_ch[c["intent_bucket"]] += 1
            ms.add(c["method_bucket"])
            if c["method_bucket"] == "other":
                other_raw[c["method"]] += 1
        for m in ms:
            meth_host[m] += 1
    order = list(P.MPP_METHODS) + ["other", "missing"]

    cats = collections.Counter((r.get("category") or "(カタログ外)") for r in dual)

    tr_path = ROOT / "data" / "trackers-latest.json"
    tr = json.loads(tr_path.read_text()) if tr_path.exists() else {}

    rc_path = ROOT / "data" / "recheck-summary.json"
    rc = json.loads(rc_path.read_text()) if rc_path.exists() else None

    own = sorted((r for r in rows if r.get("own")), key=lambda r: r["host"])

    L = []
    L.append("# dual-402-census results\n")
    L.append(f"入力: `kato9292929/endpoint` `data/endpoints_full.json.gz`（generated_at {tmeta['snapshot_generated_at']}、"
             f"{tmeta['catalog_count']:,} ルート）。測定データ: `data/{cp.name}`。分類規則と代表ルートの選び方は README を参照。\n")
    L.append("```")
    L.append(f"A1  測定日時: 開始 {both_tz(meta['started_at'])} / 終了 {both_tz(meta['finished_at'])}")
    L.append(f"A2  対象ホスト数: {len(rows):,}（うち自社ホスト {sum(1 for r in rows if r.get('own'))}）"
             + ("" if len(rows) == meta["targets"] else f"  ※対象 {meta['targets']:,} のうち記録行 {len(rows):,}"))
    L.append(f"A3  402を返したホスト数: {n402:,}（うち形式不明 {by[P.UNKNOWN_402]:,}）")
    L.append(f"A4  x402のみ: {by[P.X402_ONLY]:,}")
    L.append(f"A5  MPPのみ: {by[P.MPP_ONLY]:,}")
    L.append(f"A6  両対応: {by[P.DUAL]:,}（うち{P.WRAPPER_EST}: {wrap:,} ※推定。x402 exact と MPP tempo+evm を同じ402で並べて返すものに付けたラベルで、実装の確認はしていない）")
    L.append(f"A7  402以外・エラーの内訳: 402以外 {by[P.NOT_402]:,} / エラー {by[P.ERROR]:,}")
    for k, v in sorted(nonpay.items(), key=lambda kv: (-kv[1], kv[0])):
        L.append(f"      {k}: {v:,}")
    for lab, pred in (("HTTP 502", lambda r: r.get("status") == 502), ("エラー:dns", lambda r: r.get("error_kind") == "dns")):
        suf = collections.Counter(".".join(r["host"].split(":")[0].split(".")[-2:]) for r in rows if pred(r))
        if suf:
            L.append(f"      （参考）{lab} の多いドメイン: " + " / ".join(f"{k} {v:,}" for k, v in suf.most_common(3)))
    L.append(f"A8  MPPチャレンジのmethod内訳（両対応+MPPのみ {len(dual) + len(mpp_only):,} ホスト、チャレンジ計 {sum(meth_ch.values()):,}）")
    for m in order:
        if meth_ch[m] or m in P.MPP_METHODS:
            L.append(f"      {m}: チャレンジ {meth_ch[m]:,} / そのmethodを含むホスト {meth_host[m]:,}")
    if other_raw:
        L.append("      other の生の値: " + " / ".join(f"{k} {v:,}" for k, v in other_raw.most_common()))
    L.append("      （参考）intent: " + " / ".join(f"{k} {v:,}" for k, v in intent_ch.most_common()))
    L.append("A9  両対応ホストのカテゴリ上位5（代表ルートの endpoint カテゴリ）: "
             + (" / ".join(f"{c} {n:,}" for c, n in cats.most_common(5)) if cats else "該当なし"))
    L.append("A10 x402scan 直近30日: " + tracker_line(tr.get("x402scan")))
    L.append("A11 MPPscan 直近30日: " + tracker_line(tr.get("mppscan")))
    if rc and rc.get("done"):
        L.append(f"A12 24時間後の再確認での分類一致率: {rc['matched']}/{rc['total']} = {rc['rate_pct']}%"
                 f"（再測定 {both_tz(rc['started_at'])}、対象は初回で両対応・MPPのみのホスト。不一致の内訳は data/{rc['file']}）")
    else:
        due = rc["due_at"] if rc else None
        L.append("A12 24時間後の再確認待ち（予定日時 " + (both_tz(due) if due else "初回終了の24時間後") + "）")
    L.append("A13 自社ホストの結果:")
    for r in own:
        if r["classification"] == P.ERROR:
            detail = f"エラー({r.get('error_kind')})"
        else:
            nets = ",".join(sorted({f"{a['scheme']}@{a['network']}" for a in r["x402"]["accepts"]})) or "-"
            mm = ",".join(f"{c['method']}/{c['intent']}" for c in r["mpp"]["challenges"]) or "-"
            detail = f"HTTP {r['status']} {r['method_used']} / x402 {nets} / MPP {mm}"
        L.append(f"      {r['host']}  {r['url']}  → {r['classification']}  {detail}")
    L.append("```\n")
    L.append("ラベルの意味: 「両対応」は同じ402応答に x402（PAYMENT-REQUIRED ヘッダ、または body の x402Version+accepts）と "
             "MPP（WWW-Authenticate: Payment）の両方があるもの。「402だが形式不明」はどちらも読めなかった402。"
             "エラーはタイムアウト（10秒）・DNS・TLS・接続失敗。")
    (ROOT / "docs" / "results.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
