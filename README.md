# dual-402-census

x402 Endpoint のカタログ（`kato9292929/endpoint` の `data/endpoints_full.json.gz`）に載っている全ホストへ、**支払いをせずに**1回ずつ HTTP リクエストを送り、返ってきた 402 を x402 のみ／MPP のみ／両対応／402だが形式不明／402以外／エラー に分ける測定。結果は `docs/results.md`（A1〜A13）。

- 支払い・署名・鍵の読み込みは一切しない。`mppx` などの支払いクライアントは使わず、素の HTTP クライアント（httpx）だけで送る。
- endpoint リポジトリは読み取り専用で使う（このリポジトリにはコピーしない）。

## 対象の選び方（代表ルート）

`scripts/build_targets.py`

1. ホスト = カタログ URL の netloc（小文字。既定ポート以外はポート付き）。http/https 以外は除外。
2. ホストごとに、価格（`price.amount > 0`）が付いたルートのうち**最安**を1本選ぶ。**同額ならカタログ上の先頭**。通貨は比較に使わない（カタログ上はすべて USD 建て）。
3. 価格付きルートが1本もないホストは、カタログ上の先頭ルート。
4. 自社ホスト（`endpoint` / `jin` / `osd` / `rfq` / `probe` の各 `.x402jp.com`）はカタログになくても必ず加える。ホストが `/.well-known/x402.json` を公開している場合は、その文書に同じ規則（価格付きのうち最安、同額なら先頭）を当てて選ぶ。`{ticker}` や `:ticker` のようなテンプレート付きパスは除く（取得した文書は `data/own-discovery/` に保存）。文書もカタログ掲載もない場合は `/`。

`data/targets.jsonl` に選んだ結果（`rule` 列に、どの規則で選んだか）を残している。

## リクエスト

`census/probe.py`

- カタログ（`endpoints_full.json`）には HTTP メソッドと入力スキーマの項目がない。そのため全ルートをまず **GET** で送り、GET が 400 / 404 / 405 / 411 / 415 / 422 を返したときだけ、**POST、body は `{}`（`Content-Type: application/json`）** で1回送り直す。両方のステータスを記録する（`get_status`、`method_used`、`post_fallback`）。
- タイムアウト 10 秒（1リクエストあたりの経過時間）、全体の同時接続 8。1ホストにつき1タスクで、同じホストへのリクエストは必ず1本ずつ。リダイレクトは最大5回まで追う。
- User-Agent: `dual-402-census (+https://x402jp.com)`
- 測定は実行環境の外向きプロキシ経由。プロキシの CONNECT 失敗は DNS 失敗と接続失敗の区別がつかないので、ローカルで名前解決を試して `dns` と `connect` を分けている。

## 記録する項目（1ホスト1行、JSONL）

`data/census-<UTC>.jsonl`。最新の測定ファイル名は `data/census-latest.txt` に書いてある。

- `status`、`latency_ms`、`method_used`、`final_url`
- `x402`: `PAYMENT-REQUIRED` ヘッダの有無、ヘッダ／body の `x402Version`、`accepts` の network と scheme
- `mpp`: `WWW-Authenticate: Payment` の有無、チャレンジ数、各チャレンジの `method` / `intent`（生の値と区分の両方）、`request`（base64url の JSON）をデコードした `amount` / `currency` / `recipient`（`methodDetails.chainId` があれば `chain_id` も）、`expires`、`digest` / `opaque` の有無。1つのヘッダに複数チャレンジがある場合も、ヘッダが複数ある場合も読む。
- `other_payment_headers`: 上の2つに当てはまらない支払い関連ヘッダの名前（`Accept-Payment`、`X-Price` など）。Payment 以外の認証スキーム（例: L402）は `www-authenticate(<scheme>)` と書く。
- エラー時: `error_kind`（timeout / dns / tls / connect / other）と `error`

## 分類

`census/parse.py` の `classify`

| ラベル | 条件 |
|---|---|
| x402のみ | 402 で、x402（`PAYMENT-REQUIRED` ヘッダ、または body の `x402Version` と `accepts`）だけがある |
| MPPのみ | 402 で、`WWW-Authenticate: Payment` のチャレンジだけがある |
| 両対応 | 402 で、上の両方がある |
| 402だが形式不明 | 402 だが、どちらも読めない（body の先頭400字を `body_excerpt` に保存） |
| 402以外 | 402 以外のステータス |
| エラー | タイムアウト・DNS・TLS・接続失敗 |

両対応のうち、x402 の `exact` と MPP の `tempo` と `evm` を同じ 402 で並べて返すものには「**mppxのx402互換ラッパー由来と推定**」（`wrapper_estimate: true`）を付ける。応答の形から付けたラベルで、実装を確かめたものではない。

## 公開トラッカー

`scripts/trackers.py`（Playwright）。x402scan のトップページにある「Overall Stats / Past 30 Days」と、MPPscan の「Usage」（All・30d）の画面上の値を、取得日時と一緒に `data/trackers-*.json` に記録し、スクリーンショットを `docs/screens/` に保存する。期間の選択を画面上で確認できなかった値や読めなかった値は「取得できず」と書き、推定値では埋めない。MPPscan の買い手数は、画面上のラベル「Agents」の値を記録している。

## 実行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_targets.py ../endpoint/data/endpoints_full.json.gz
.venv/bin/python scripts/probe.py                    # 全ホスト（数時間かかる）
PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers .venv/bin/python scripts/trackers.py
.venv/bin/python scripts/recheck.py --plan           # 24時間後の予定時刻を記録
.venv/bin/python scripts/aggregate.py                # docs/results.md を出力
# 24時間後:
.venv/bin/python scripts/recheck.py                  # 両対応とMPPのみのホストだけ測り直し、A12 を更新
.venv/bin/pytest -q tests
```

## 24時間後の再確認

`scripts/recheck.py` は、初回の測定で両対応またはMPPのみに分類されたホストだけを、同じ代表ルート・同じ条件でもう一度測り、分類が一致した割合を `data/recheck-summary.json` と A12 に書く。予定時刻は「それらのホストを初回に測った時刻のうち最も遅いもの + 24時間」。それより前に実行しても止まる（`--force` を付ければ実行できる）。
