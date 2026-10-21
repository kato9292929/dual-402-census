# dual-402-census results

入力: `kato9292929/endpoint` `data/endpoints_full.json.gz`（generated_at 2026-10-19T13:10:36.794Z、161,826 ルート）。測定データ: `data/census-20261020T072707Z.jsonl`。分類規則と代表ルートの選び方は README を参照。

```
A1  測定日時: 開始 2026-10-20 07:27:07 UTC / 2026-10-20 16:27:07 JST / 終了 2026-10-20 07:56:09 UTC / 2026-10-20 16:56:09 JST
A2  対象ホスト数: 13,748（うち自社ホスト 5）
A3  402を返したホスト数: 3,732（うち形式不明 187）
A4  x402のみ: 3,211
A5  MPPのみ: 0
A6  両対応: 334（うちmppxのx402互換ラッパー由来と推定: 25 ※推定。x402 exact と MPP tempo+evm を同じ402で並べて返すものに付けたラベルで、実装の確認はしていない）
A7  402以外・エラーの内訳: 402以外 7,893 / エラー 2,123
      HTTP 502: 5,469
      エラー:dns: 1,496
      HTTP 404: 1,487
      エラー:timeout: 313
      HTTP 200: 232
      HTTP 4xx: 211
      HTTP 503: 211
      エラー:connect: 160
      HTTP 5xx: 138
      エラー:tls: 138
      HTTP 500: 44
      HTTP 405: 39
      HTTP 401: 36
      HTTP 403: 25
      エラー:other: 16
      HTTP 429: 1
      （参考）HTTP 502 の多いドメイン: lhr.life 5,062 / hergertsynthora.com 173 / serveousercontent.com 153
      （参考）エラー:dns の多いドメイン: pinggy-free.link 528 / pinggy.net 493 / trycloudflare.com 68
A8  MPPチャレンジのmethod内訳（両対応+MPPのみ 334 ホスト、チャレンジ計 452）
      tempo: チャレンジ 226 / そのmethodを含むホスト 212
      stripe: チャレンジ 30 / そのmethodを含むホスト 30
      evm: チャレンジ 112 / そのmethodを含むホスト 105
      lightning: チャレンジ 1 / そのmethodを含むホスト 1
      solana: チャレンジ 19 / そのmethodを含むホスト 19
      other: チャレンジ 49 / そのmethodを含むホスト 27
      missing: チャレンジ 15 / そのmethodを含むホスト 15
      other の生の値: x402 18 / x402-exact 18 / usdc 6 / exact 3 / GET 2 / asterpay 1 / stripe-card-prepaid 1
      （参考）intent: charge 406 / other 23 / missing 16 / session 7
A9  両対応ホストのカテゴリ上位5（代表ルートの endpoint カテゴリ）: search 84 / messaging 73 / compute 73 / data 56 / trading 25
A10 x402scan 直近30日: 取引額 $1.23M / 件数 3.03M / 買い手数 36.05K（画面ラベル: Buyers） / 期間 Past 30 Days / 取得日時 2026-10-20 05:53:39 UTC / 2026-10-20 14:53:39 JST / スクリーンショット `docs/screens/x402scan-20261020T055328Z.png`
A11 MPPscan 直近30日: 取引額 $8.65K / 件数 843K / 買い手数 12.3K（画面ラベル: Agents） / 期間 30d / 取得日時 2026-10-20 05:53:53 UTC / 2026-10-20 14:53:53 JST / スクリーンショット `docs/screens/mppscan-30d-all-20261020T055328Z.png`
A12 24時間後の再確認での分類一致率: 330/334 = 98.8%（再測定 2026-10-21 07:58:29 UTC / 2026-10-21 16:58:29 JST、対象は初回で両対応・MPPのみのホスト。不一致の内訳は data/recheck-20261021T075829Z.jsonl）
A13 自社ホストの結果:
      endpoint.x402jp.com  https://endpoint.x402jp.com/  → 402以外  HTTP 200 GET / x402 - / MPP -
      jin.x402jp.com  https://jin.x402jp.com/api/jin/series  → x402のみ  HTTP 402 GET / x402 exact@solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp / MPP -
      osd.x402jp.com  https://osd.x402jp.com/api/alpha/portfolio/current  → x402のみ  HTTP 402 GET / x402 exact@solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp / MPP -
      probe.x402jp.com  https://probe.x402jp.com/  → 402以外  HTTP 200 GET / x402 - / MPP -
      rfq.x402jp.com  https://rfq.x402jp.com/  → 402以外  HTTP 200 GET / x402 - / MPP -
```

ラベルの意味: 「両対応」は同じ402応答に x402（PAYMENT-REQUIRED ヘッダ、または body の x402Version+accepts）と MPP（WWW-Authenticate: Payment）の両方があるもの。「402だが形式不明」はどちらも読めなかった402。エラーはタイムアウト（10秒）・DNS・TLS・接続失敗。
