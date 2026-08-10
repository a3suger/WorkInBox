# WorkInBox タグ・外部案件取り込み・将来データ管理メモ

この文書は、タグ設計、Thunderbird 連携、自分宛て備忘メール、外部形式との関係についての補足設計メモである。

正式なワークフローは `docs/design_workflow.md`、締切登録支援の詳細は `docs/deadline_support_discussion_2026-08-10.md` を参照する。

---

## 1. Thunderbird タグ連携

WorkInBox の作業タグは IMAP keyword を正本とし、Thunderbird からも直接付け外しできることを重視する。

主なタグ:

- `重要`
- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`
- `判定保留`
- `締切登録済み`
- `スケジュール対応済み`
- `返信待ち`
- `対応待ち`
- `依頼済み`
- `一括処理`

Thunderbird MailExtension は固定 key に対して日本語表示名、色、キーボード順序を定義する薄い接着層として扱う。

Extension に業務ロジックや WorkInBox の正本データを持たせない。

---

## 2. 参照タグ `重要`

`重要` は作業状態ではなく参照価値を示すタグである。

- アーカイブ後も保持してよい。
- スターとは独立する。
- `一括処理` や各作業タグと共存してよい。

---

## 3. Thunderbird のキーボード操作

先頭 6 タグの想定順序:

1. `重要`
2. `締切あり`
3. `スケジュール調整`
4. `回答必要`
5. `読む・検討`
6. `判定保留`

WorkInBox は利用者独自の Thunderbird タグを勝手に削除・上書きしない。

---

## 4. 自分宛て備忘メール

LINE、Teams、Slack、口頭等で発生した仕事を、利用者が自分宛てメールとして WorkInBox に取り込む運用を正式な入力経路として扱う。

`From` が利用者自身であることだけで `返信待ち` と判断してはいけない。

自分発メールには少なくとも次がある。

1. 自分宛て備忘メール
2. 相手への送信メールの自分宛てコピー等
3. 支援者への依頼メール

入口・目的判定は将来 TriageBox が担当する。

現時点では TrackingBox 対象のスターは利用者が Thunderbird 上で付与する。

---

## 5. Thunderbird Extension の役割

Extension は Thunderbird 固有 API が必要な UI / 接続処理だけを担当する。

想定役割:

- WorkInBox タグ定義の登録
- WorkInBox Web UI を Thunderbird 内で開く
- WorkInBox の一覧から該当メールを Thunderbird で開く

概念構成:

```text
Thunderbird
  ├─ メール閲覧・返信・タグ操作
  ├─ read-only ICS / VTODO の閲覧
  └─ WorkInBox Web UI
          ↓
Thunderbird Extension
          ↓
WorkInBox
  ├─ FastAPI / Jinja2
  ├─ Application Service
  ├─ IMAP
  └─ SQLite
```

---

## 6. 正本の整理

用途ごとに正本を分ける。

- メール本体: メールサーバ
- WorkInBox 作業タグ: IMAP keyword
- WorkInBox 内部状態: SQLite
- 正式登録された締切: SQLite
- Thunderbird 向け VTODO: SQLite から生成した派生表現

**v0.2 の締切 ICS は読み取り専用である。**

Thunderbird 側で VTODO を編集しても WorkInBox へ逆同期しない。

CalDAV は v0.2 では導入しない。

---

## 7. 締切データと iCalendar / VTODO

正式締切は SQLite に保存する。

WorkInBox は SQLite の内容から `deadlines.ics` を生成し、Thunderbird が購読する。

```text
SQLite
  └─ deadlines
       ↓ generate
   deadlines.ics
       ↓ subscribe (read-only)
   Thunderbird
```

`.ics` は SQLite から何度でも再生成できる。

各 VTODO の `UID` は SQLite の deadline id から安定生成する。

例:

```text
UID:wib-deadline-123@workinbox
```

VTODO には元メールを探しやすくするため、Message-ID、メール日時、差出人、件名等を `DESCRIPTION` に入れる。

補助的な機械可読情報として `X-WORKINBOX-*` プロパティを付けてもよい。

---

## 8. バックアップと可搬性

SQLite が正本であることと、可搬形式を持つことは両立する。

`.ics` は Thunderbird 表示用の派生データであると同時に、人間が内容を確認しやすい交換形式でもある。

ただし、v0.2 では `.ics` から SQLite を自動復元することや双方向同期を必須としない。

SQLite 自体のバックアップは別途必要である。

SQLite ファイルを OneDrive 等の同期フォルダ上に置き、複数 PC から同時に直接書き込む方式は採用しない。

---

## 9. 将来の双方向連携

将来、Thunderbird から締切日時変更・完了操作等を行い、それを WorkInBox に反映する必要が明確になった場合は、CalDAV 等の双方向方式を検討する。

その場合は以下が新たに必要になる。

- 書き込み可能なサーバ側リソース
- 更新競合の扱い
- SQLite と外部編集の同期規則
- 複数 PC の競合解決

v0.2 ではこれらを持ち込まない。

---

## 10. v0.2 と将来拡張の境界

### v0.2

- IMAP タグ読み書き
- Thunderbird タグ定義
- 自分宛て備忘メールを考慮した設計
- 締切候補抽出・確認・修正・却下
- 複数締切対応
- SQLite への正式締切保存
- Message-ID 単位の締切関連付け
- SQLite から read-only ICS / VTODO 生成
- Thunderbird での ICS 購読

### v0.2 以後

- CalDAV
- Thunderbird から SQLite への逆同期
- メールスレッド / 案件単位の Context
- Context 単位の関連締切一覧
- 複数 PC の双方向同期
- メモ等の追加交換形式

---

## 11. 未決事項

- ICS の提供 URL / ファイル配置方法
- Thunderbird 側の購読設定手順
- `DESCRIPTION` と `X-WORKINBOX-*` の最終フォーマット
- メール本文で明示された特殊なタイムゾーンの扱い
- 将来 Context を導入する場合のグルーピング規則
- CalDAV を導入する条件
