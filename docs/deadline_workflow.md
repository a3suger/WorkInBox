# 締切登録支援 詳細設計

この文書は `docs/design.md` の締切 / 締切登録支援を実装へ落とすための現行詳細設計である。

正式仕様との矛盾がある場合は `docs/design.md` を優先する。

## 役割

締切登録支援は専用ワークフローであり、WIB で進める。

- 締切データの正本は SQLite とする。
- Thunderbird 向け `.ics` / VTODO は SQLite から生成する派生データとする。
- 締切は `source_message_id` で元メールを参照する。
- 元メールを開く場合は共通の Thunderbird Bridge を利用する。

## 候補

1通のメールから0件以上の締切候補を扱う。

利用者は候補ごとに次を行える。

- 登録する
- 登録しない
- 修正する
- AI候補とは別に候補を追加する

AI抽出結果だけで締切ワークフローを自動終了しない。

## 候補が1件以上ある場合

未判断候補が残っている間は締切ワークフローを継続する。

すべての候補について利用者判断が終わった後:

```text
1件以上を正式登録
  -> 締切登録済み を付与

全候補を登録しない
  -> 締切あり を解除
     締切登録済み は付けない
```

## AI候補が0件の場合

AIが候補を0件としたことだけでは `締切あり` を解除しない。

```text
締切あり + ★
  ↓ AI抽出
候補0件
  ↓
締切あり + ★ を維持
```

利用者は本文を確認して次のどちらかを行う。

- 締切がある: `＋ 締切を追加` で候補を追加する。
- 締切がない: `締切なしとして終了` を明示的に実行する。

`このメールには締切なしとして終了` は、未確定候補が存在する場合も利用できる。この操作は未確定候補をすべて `登録しない` とし、メール全体について締切登録支援を終了する。正式登録済みの締切が存在する場合は利用できない。

明示終了時:

```text
締切あり を解除
  ↓
専用ワークフロー終了時の共通遷移
```

## 専用ワークフロー終了時の共通遷移

締切登録支援が完了または非該当として終了した直後、メール全体の残作業を評価する。

```text
他の専用ワークフローが未終了
  -> その専用ワークフローを継続

専用ワークフローがすべて終了
AND 通常ワークフローあり
  -> 確定済みの通常ワークフローを継続

専用ワークフローがすべて終了
AND 通常ワークフローなし
  -> 一括処理 + ☆
```

`一括処理 + ☆` へ移った場合、SQLite tracking status も inactive/unstarred とする。

## 元メール参照

正式締切は Record の有無に依存せず、`deadline.source_message_id` で元メールを参照する。

元メールは INBOX にない可能性があるため、Thunderbird Bridge 側では `docs/design.md` の Message-ID 検索規則に従う。

各VTODOの主URLには `mid:{Message-ID}` を付ける。Thunderbirdのカレンダー／ToDo画面は `mid:` を内部処理し、元メールを直接表示する。説明欄には `/deadlines/{deadline_id}` の「締切の確認・修正」URLも付け、WIB側で正式締切のタイトル・期限・メモを修正できるようにする。SQLiteを正本として保存した修正内容は、次に `.ics` / VTODOを取得した際に反映される。従来の `/deadlines/{deadline_id}/source-message` は既存VTODOとの互換用に維持する。

概念上の検索順:

```text
1. INBOX
2. 元メール送信年月に対応する Archive
```

## 実装対応

主な実装:

- `src/workinbox/deadline_application.py`: AI候補抽出
- `src/workinbox/application.py`: 候補 / 正式締切データ操作
- `src/workinbox/deadline_workflow.py`: 候補判断後の完了判定と共通終了遷移
- `src/workinbox/deadline_ics.py`: read-only `.ics` / VTODO
- `src/workinbox/templates/deadlines.html`: WIB 締切登録支援 UI
- `src/workinbox/templates/deadline_detail.html`: 正式締切の確認・修正 UI
- `src/workinbox/templates/deadline_source_message.html`: VTODOから開く元メール案内とBridge自動接続

## 履歴

2026-08-10 時点の設計議論は `deadline_support_discussion_2026-08-10.md` に残す。現在仕様の判断にはこの文書と `docs/design.md` を使用する。
