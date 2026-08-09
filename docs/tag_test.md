# WorkInBox タグを Thunderbird で利用できるかの確認テスト

## 1. 目的

このテストの目的は、**WorkInBox が先に決めたタグを Thunderbird でも同じタグとして利用できるか**を確認することである。

今回確認する構成は次のとおり。

```text
WorkInBox がタグを定義する
        ↓
Thunderbird に同じ key のタグ定義を登録する
        ↓
Thunderbird で日本語表示名として表示・付与・解除できる
        ↓
IMAP 上には WorkInBox が決めた key が保存される
        ↓
WorkInBox からも同じ key を読み書きできる
```

つまり、Thunderbird が作ったタグを WorkInBox が後から調べて合わせる方式ではない。

**WorkInBox がタグ定義の基準を持ち、Thunderbird はそのタグを表示・操作する。**

この方針は `docs/design_notes_tags_and_external_intake.md` に基づく。

---

## 2. 1タグでの相互運用テスト

最初の検証には `締切あり` を使用した。

| 項目 | 値 |
| --- | --- |
| WorkInBox key | `wib-deadline` |
| Thunderbird 表示名 | `締切あり` |

テスト用 Thunderbird MailExtension を使い、`wib-deadline` を Thunderbird のローカルタグ定義へ登録した。

確認した流れは次のとおり。

1. WorkInBox 側で `wib-deadline` を定義する。
2. Extension から Thunderbird に `wib-deadline` / `締切あり` を登録する。
3. Thunderbird で `締切あり` を付ける。
4. IMAP FLAGS に `wib-deadline` が保存されることを確認する。
5. Thunderbird でタグを外すと IMAP FLAGS から `wib-deadline` が消えることを確認する。
6. WorkInBox の診断CLIから `wib-deadline` を追加する。
7. Thunderbird 上で `締切あり` と表示されることを確認する。
8. WorkInBox の診断CLIから `wib-deadline` を削除する。
9. Thunderbird 上でも `締切あり` が外れることを確認する。

### 結果

**すべて成功した。**

したがって、次の双方向相互運用が成立することを実機で確認できた。

```text
Thunderbird → IMAP → WorkInBox
WorkInBox   → IMAP → Thunderbird
```

また、WorkInBox 側の IMAP 書き込みは FLAGS 全体を置換せず、対象 keyword のみを `+FLAGS.SILENT` / `-FLAGS.SILENT` で追加・削除する方式とする。

---

## 3. 採用する基本方式

1タグでの検証成功を受け、以下の方式を採用する。

- WorkInBox が IMAP keyword を正式定義する。
- WorkInBox 用 keyword は `wib-` prefix を使う。
- Thunderbird Extension は同じ key に対する表示名と色を登録する。
- Thunderbird での人手によるタグ付与・解除を許容する。
- WorkInBox は自分が管理する `wib-*` keyword だけを変更する。
- Thunderbird 標準flagや利用者独自タグを勝手に削除・上書きしない。

---

## 4. 12タグの正式候補

以下を現時点の正式候補とする。

| 種別 | 正式 key | 表示名 | 色案 |
| --- | --- | --- | --- |
| 参照 | `wib-important` | `重要` | `#7B1FA2` |
| 作業 | `wib-deadline` | `締切あり` | `#D32F2F` |
| 作業 | `wib-schedule` | `スケジュール調整` | `#F57C00` |
| 作業 | `wib-answer` | `回答必要` | `#1976D2` |
| 作業 | `wib-review` | `読む・検討` | `#039BE5` |
| 判定状態 | `wib-pending` | `判定保留` | `#757575` |
| 処理完了 | `wib-deadline-done` | `締切登録済み` | `#8E2424` |
| 処理完了 | `wib-schedule-done` | `スケジュール対応済み` | `#A65300` |
| 待機 | `wib-waiting-reply` | `返信待ち` | `#388E3C` |
| 待機 | `wib-waiting-action` | `対応待ち` | `#7CB342` |
| 履歴 | `wib-requested` | `依頼済み` | `#795548` |
| 終了 | `wib-batch` | `一括処理` | `#424242` |

色は Thunderbird 上で実際に見たうえで微調整してよいが、key と表示名はこの候補を基準に実装を進める。

---

## 5. 色の考え方

色は意味の近い状態を同系統にする。

- `締切あり` / `締切登録済み`: 赤系
- `スケジュール調整` / `スケジュール対応済み`: オレンジ系
- `回答必要`: 青
- `読む・検討`: 水色
- `返信待ち` / `対応待ち`: 緑系
- `判定保留`: グレー
- `重要`: 紫
- `依頼済み`: 茶
- `一括処理`: 濃いグレー

処理前と処理後は同系統の色にしつつ、Thunderbird の一覧で識別できる程度に差を付ける。

---

## 6. Thunderbird 数字キー配置

人が直接修正する頻度が高いタグについては、以下の配置を採用する。

```text
1 = 重要
2 = 締切あり
3 = スケジュール調整
4 = 回答必要
5 = 読む・検討
6 = 判定保留
```

Thunderbird 140 系の `messages.tags.update()` が扱える `ordinal` を使い、Extension がこの6タグを先頭へ配置する。

完了・待機・履歴・終了系のタグは主要な数字キー枠に入れない。

---

## 7. `重要` の既存タグについて

既存 Thunderbird の `重要` タグ移行は、相互運用方式そのものとは分けて扱う。

今後、以下を確認する。

- 現在使っている `重要` の IMAP keyword。
- 既存 key をそのまま使うか。
- `wib-important` へ移行するか。
- 移行する場合、既存メールに付いたタグをどう変換するか。

基本方式の成立はすでに `wib-deadline` で確認済みなので、この調査は v0.2 のタグ相互運用方式を採用する前提条件ではない。

---

## 8. 実装状況

相互運用方式の検証は完了し、v0.2 の IMAP タグ読み書き基盤まで実装した。

実装済み:

1. 12タグの正式 key / 表示名 / 色を `src/workinbox/work_tags.py` に定義。
2. Thunderbird Extension で同じ12タグを登録し、主要6タグを数字キー対象の先頭へ配置。
3. SQLite に保存済みの mailbox / UIDVALIDITY / UID を使い、IMAP FLAGS から現在の WIB タグを読み取る。
4. Web UI から対象の WIB keyword だけを `+FLAGS.SILENT` / `-FLAGS.SILENT` で追加・削除する。
5. タグ書き込み前に UIDVALIDITY を照合し、保存済み識別情報が古い場合は書き込みを中止する。
6. Web UI の `未取得` 表示を、実際の IMAP タグ表示とタグ変更UIへ置き換える。

作業タグの正本は引き続き IMAP とし、SQLite にタグ状態を独立した正本として保存しない。

次の実装段階は、AI 初期分類結果を同じ WorkInBox tag key へ反映する処理である。
