# dual-402-census results

入力: `kato9292929/endpoint` `data/endpoints_full.json.gz`（generated_at 2026-10-19T13:10:36.794Z、161,826 ルート）。測定データ: `data/partial.jsonl`。分類規則と代表ルートの選び方は README を参照。

```
A1  測定日時: 開始 2026-10-20 05:51:16 UTC / 2026-10-20 14:51:16 JST / 終了 2026-10-20 05:51:16 UTC / 2026-10-20 14:51:16 JST
A2  対象ホスト数: 280（うち自社ホスト 0）  ※対象 13,748 のうち記録行 280
A3  402を返したホスト数: 20（うち形式不明 0）
A4  x402のみ: 19
A5  MPPのみ: 0
A6  両対応: 1（うちmppxのx402互換ラッパー由来と推定: 0 ※推定。x402 exact と MPP tempo+evm を同じ402で並べて返すものに付けたラベルで、実装の確認はしていない）
A7  402以外・エラーの内訳: 402以外 25 / エラー 235
      エラー:timeout: 209
      HTTP 404: 17
      エラー:dns: 13
      エラー:tls: 8
      エラー:connect: 5
      HTTP 502: 3
      HTTP 503: 2
      HTTP 200: 1
      HTTP 403: 1
      HTTP 5xx: 1
A8  MPPチャレンジのmethod内訳（両対応+MPPのみ 1 ホスト、チャレンジ計 1）
      tempo: チャレンジ 0 / そのmethodを含むホスト 0
      stripe: チャレンジ 0 / そのmethodを含むホスト 0
      evm: チャレンジ 0 / そのmethodを含むホスト 0
      lightning: チャレンジ 0 / そのmethodを含むホスト 0
      solana: チャレンジ 0 / そのmethodを含むホスト 0
      other: チャレンジ 1 / そのmethodを含むホスト 1
      other の生の値: x402 1
      （参考）intent: charge 1
A9  両対応ホストのカテゴリ上位5（代表ルートの endpoint カテゴリ）: data 1
A10 x402scan 直近30日: 取引額 $1.23M / 件数 3.03M / 買い手数 36.05K（画面ラベル: Buyers） / 期間 Past 30 Days / 取得日時 2026-10-20 05:53:39 UTC / 2026-10-20 14:53:39 JST / スクリーンショット `docs/screens/x402scan-20261020T055328Z.png`
A11 MPPscan 直近30日: 取引額 $8.65K / 件数 843K / 買い手数 12.3K（画面ラベル: Agents） / 期間 30d / 取得日時 2026-10-20 05:53:53 UTC / 2026-10-20 14:53:53 JST / スクリーンショット `docs/screens/mppscan-30d-all-20261020T055328Z.png`
A12 24時間後の再確認待ち（予定日時 初回終了の24時間後）
A13 自社ホストの結果:
```

ラベルの意味: 「両対応」は同じ402応答に x402（PAYMENT-REQUIRED ヘッダ、または body の x402Version+accepts）と MPP（WWW-Authenticate: Payment）の両方があるもの。「402だが形式不明」はどちらも読めなかった402。エラーはタイムアウト（10秒）・DNS・TLS・接続失敗。
