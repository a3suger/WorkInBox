# WorkInBox v0.2 設計メモ

## 1. 目的

v0.2 では、v0.1 のメール追跡基盤を拡張し、TrackingBox の主要フローを成立させる。

主な対象:

- 新規メール取り込み範囲の制限
- active / inactive 追跡状態
- FastAPI + Jinja2 Web UI
- IMAP 作業タグ読み書き
- AI 初期分類
- 判定保留 UI
- Thunderbird Bridge
- 締切登録支援
- スケジュール調整支援
- 特殊処理後の次作業提案

---

## 2. 正本の扱い

用途ごとに正本を分ける。

- メール本体: メールサーバ
- 作業タグ: IMAP keyword
- WorkInBox 内部状態: SQLite
- 正式締切: SQLite
- Thunderbird 向け締切表示: SQLite から生成した read-only `.ics` / VTODO

v0.2 では CalDAV を導入しない。

Thunderbird 側で行われた VTODO 編集を SQLite へ逆同期しない。

---

## 3. 対象 mailbox とメール識別

v0.2 では設定された 1 mailbox を対象とする。

IMAP 操作対象:

- mailbox
- UIDVALIDITY
- UID

論理的な同一メール判定:

- Message-ID

新規探索で同じ Message-ID が既に SQLite に存在する場合、原則として既存レコードを利用する。

---

## 4. 新規取り込みと追跡状態

新規取り込みは、

- 対象 mailbox 内
- スター付き
- 過去 N 日以内

を満たすメールに限定する。

N は新規探索だけに適用し、一度取り込んだメールは N 日を超えても追跡を継続する。

追跡状態:

- `active`
- `inactive_unstarred`
- `inactive_moved`

正常な IMAP 応答で状態変化を確認した場合は即時反映する。

IMAP 処理自体が失敗した場合は、その失敗を理由に inactive にしない。

---

## 5. Web UI

技術構成:

- FastAPI
- Jinja2
- サーバーサイド HTML レンダリング

FastAPI route に IMAP / SQLite の業務ロジックを直接持たせず、Application Service を介する。

主な UI:

- active 一覧
- inactive 一覧
- 通常同期
- 全件再確認
- タグ確認・変更
- 判定保留一覧
- 締切登録支援
- スケジュール調整支援

---

## 6. 作業タグ

初期作業タグ:

- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`

例外的判定状態:

- `判定保留`

処理完了:

- `締切登録済み`
- `スケジュール対応済み`

その他:

- `重要`
- `返信待ち`
- `対応待ち`
- `依頼済み`
- `一括処理`

作業タグの正本は IMAP keyword とする。

---

## 7. AI 初期分類

基本順序:

1. `締切あり` を再現率重視で判定
2. `スケジュール調整` を独立して再現率重視で判定
3. どちらか該当すればそのタグを付与し、回答 / 読む・検討には進まない
4. 該当しなければ `回答必要` を再現率重視で判定
5. 該当すれば `回答必要`
6. いずれにも該当しない場合は `読む・検討`
7. 分類材料自体が不足している場合のみ `判定保留`

`判定保留` は通常の曖昧さのフォールバックではない。

---

## 8. 判定保留

`判定保留` メールを専用一覧に表示し、利用者が次のいずれかへ再分類する。

- `締切あり`
- `スケジュール調整`
- `締切あり` + `スケジュール調整`
- `回答必要`
- `読む・検討`

確定後は `判定保留` を外し、選択したタグを IMAP に付与する。

---

## 8.5. Thunderbird Bridge

詳細は `docs/thunderbird_bridge.md` を参照する。

WorkInBox Web UI と Thunderbird Extension の間に、Thunderbird 固有操作を行うための薄い共通ブリッジを置く。

### 必須 PoC

v0.2 の締切登録支援に入る前に、次を成立させる。

1. Thunderbird Extension からローカルの WorkInBox Web UI を Thunderbird の content tab で開く。
2. WorkInBox Web UI の操作から Message-ID を Extension へ渡す。
3. Extension が Thunderbird messages API で `headerMessageId` を使って該当メールを解決する。
4. 解決した元メールを通常の message display で開く。

Message-ID は WorkInBox と Thunderbird を結ぶ長期的な論理リンクキーとする。

Thunderbird 内部の一時的な message id、folder UID 等を WorkInBox 側の長期リンクとして保存しない。

### Gloda / Conversation との分離

`Message-ID -> MessageHeader -> 通常のメール表示` を Bridge の必須基盤とする。

Conversation 表示は Thunderbird 128 / 140 系で実装方法と Gloda 依存性を確認した上で追加する。

Global Search / Gloda の索引状態が不完全でも元メールへ戻れることを優先し、Conversation 表示の失敗を `Open in Thunderbird` 全体の失敗とはしない。

### Archive 索引ポリシー

Archive 配下では Thunderbird の Favorite 状態を、Global Search / Gloda の索引対象を示す利用者入力として利用する。

```text
Archive 配下
    ├─ Favorite = ON  → indexing ON
    └─ Favorite = OFF → indexing OFF
```

Favorite 状態の取得・変更など標準 MailExtension API で可能な処理は標準 API を使う。

Gloda の indexing ON / OFF が標準 API で扱えない場合、その処理だけを最小の Experiment API に閉じ込める。

初期実装では Favorite の変更を常時監視せず、設定画面等から現在状態を確認して手動同期する PoC でよい。

### 利用箇所

Bridge は機能ごとに個別実装せず、共通の `Open in Thunderbird` として再利用する。

主な利用箇所:

- 判定保留
- 締切候補
- 正式締切
- スケジュール調整
- 返信待ち / 対応待ち

---

## 9. 締切登録支援

詳細は `docs/deadline_support_discussion_2026-08-10.md` を参照する。

### 対象

- `締切あり`
- `締切登録済み` なし

### AI 候補

AI は 1 通から 0〜複数の締切候補を抽出する。

AI が締切の存在を認識しても日時を特定できない場合は、日付未確定候補として残す。

確信度が低い推定は `要確認` として利用者へ明示する。

### 利用者操作

各候補:

- 登録しない
- 修正する
- 登録する
- Thunderbird で元メールを開く

さらに `＋ 締切を追加` を用意する。

### SQLite

作業中候補は再開のため一時保存してよい。

正式登録された締切は SQLite に長期保持する。

v0.2 では起点メールとの関連を Message-ID 単位で保持する。

### 完了条件

すべての候補について判断が完了し、1 件以上正式登録された場合に `締切登録済み` を自動付与する。

全候補を却下した場合は `締切あり` を削除し、`締切登録済み` は付けない。

### 日時

- 日付のみなら日付締切
- 時刻明示なら時刻まで保持
- タイムゾーンは設定値を基本とする
- 年省略時はメール送信日時以後の最初の該当日付として補完

### ICS / VTODO

SQLite の正式締切から read-only `.ics` を生成する。

Thunderbird はこれを購読して閲覧する。

VTODO の UID は SQLite の deadline id から安定生成する。

例:

```text
UID:wib-deadline-123@workinbox
```

DESCRIPTION には Message-ID、Mail-Date、From、Subject 等の元メール情報を含める。

---

## 10. スケジュール調整支援

対象:

- `スケジュール調整`
- `スケジュール対応済み` なし

利用者は、

- 自分で対応
- 支援者へ依頼

のいずれかを選ぶ。

支援者へ依頼した場合:

- 元メールに `依頼済み`
- 依頼メールにスター + `対応待ち`
- 回答後に必要な反映を終えた時点で元メールに `スケジュール対応済み`

---

## 11. 特殊処理完了後

`締切あり` と `スケジュール調整` が重複する場合、それぞれの完了条件を独立に確認する。

必要なすべての特殊処理が完了した後に一度だけ AI が次処理を提案する。

主な候補:

- `回答必要`
- `一括処理`

AI は自動確定せず、利用者が最終判断する。

---

## 12. v0.2 で扱わないもの

- CalDAV
- Thunderbird から SQLite への締切逆同期
- メールスレッド / 案件単位の Context
- Context 単位の関連締切一覧
- 複数 PC の同時 SQLite 書き込み
- 独自の汎用 TODO / プロジェクト管理 UI

---

## 13. 将来拡張

- `In-Reply-To` / `References` を利用した Context
- Context に関連する締切一覧
- 複数メールから同一 Context への締切追加
- CalDAV 等による双方向編集
- 複数 PC の競合解決

---

## 14. 関連文書

- `docs/design_workflow.md`
- `docs/thunderbird_bridge.md`
- `docs/deadline_support_discussion_2026-08-10.md`
- `docs/design_notes_tags_and_external_intake.md`
- `docs/roadmap.md`
