# WorkInBox Documentation Guide

このファイルを `docs/` 配下の設計文書の**入口**とする。

開発・設計を行う際は、個々の文書を直接指定するのではなく、まずこのファイルを読み、作業内容に応じてここからリンクされた文書を参照する。

## 開発時の読み方

原則として次の順序で読む。

1. [全体設計](design.md)
2. [正式ワークフロー](design_workflow.md)
3. [現在のロードマップ](roadmap.md)
4. 作業対象に対応する詳細設計

実装時に仕様が複数文書へまたがる場合も、このファイルを起点として必要な文書を辿る。

文書間に矛盾がある場合は、次の優先順位で扱う。

1. `design_workflow.md` の確定済みワークフロー
2. 現在バージョンの設計 (`design_v0_2.md` など)
3. 機能別の詳細設計・議論メモ
4. 古いバージョンの設計・検証記録

矛盾を発見した場合は、実装側で勝手に解釈せず文書を更新して整合させる。

---

## 中核ドキュメント

### [design.md](design.md)

WorkInBox の目的、責務境界、正本の考え方などを短くまとめた全体設計。

最初に「WorkInBox が何をする/しないか」を確認するための文書。

### [design_workflow.md](design_workflow.md)

TrackingBox / TriageBox、タグ体系、特殊処理、締切登録支援、スケジュール調整支援などの**正式な業務ワークフロー**。

業務ロジックを変更する場合は必ず参照する。

### [roadmap.md](roadmap.md)

現在の実装状況と、次に実装する順序。

「次に何を作るか」を判断する場合はこの文書を参照する。

### [design_v0_2.md](design_v0_2.md)

v0.2 の技術的な境界、追跡状態、FastAPI、IMAP、SQLite、締切登録支援などの設計。

v0.2 実装を変更する場合に参照する。

---

## 機能別詳細

### [ai_initial_classification.md](ai_initial_classification.md)

AI 初期分類の判定順序、出力、再現率重視の考え方、`判定保留` の条件。

AI 分類を変更する場合に参照する。

### [deadline_support_discussion_2026-08-10.md](deadline_support_discussion_2026-08-10.md)

締切登録支援の詳細設計。

主な内容:

- 1 メールから複数締切
- AI が日時を抽出できない候補
- `登録しない / 修正する / 登録する`
- 利用者による締切追加
- SQLite を締切データの正本とする方針
- read-only ICS / VTODO
- Message-ID による元メール関連付け
- Context は v0.2 以後

### [thunderbird_bridge.md](thunderbird_bridge.md)

WorkInBox Web UI と Thunderbird Extension の共通ブリッジ設計。

主な内容:

- FastAPI は WorkInBox 本体/UI/APIとして独立して動かす
- Extension は Thunderbird 固有 API だけを担当する
- Message-ID から Thunderbird 内のメールを検索する
- WorkInBox の画面から元メール / Conversation を開く
- 締切・判定保留・返信待ち等で同じ仕組みを再利用する

### [design_notes_tags_and_external_intake.md](design_notes_tags_and_external_intake.md)

Thunderbird タグ、Extension、自分宛て備忘メール、ICS、将来の外部形式等に関する補足設計。

### [thunderbird_tag_backup_restore.md](thunderbird_tag_backup_restore.md)

Thunderbird タグ定義のバックアップ/復元に関する運用資料。

---

## 履歴・検証資料

### [design_v0_1.md](design_v0_1.md)

v0.1 の設計記録。現在仕様ではなく、過去の判断を確認するための資料。

### [tag_test.md](tag_test.md)

Thunderbird / IMAP タグ相互運用の検証記録。

---

## 現在の重要なアーキテクチャ判断

### 正本

- メール本体: メールサーバ
- WorkInBox 作業タグ: IMAP keyword
- WorkInBox 内部状態: SQLite
- 正式締切: SQLite
- Thunderbird 向け締切: SQLite から生成する read-only `.ics` / VTODO

### Thunderbird との境界

- Thunderbird: メールの閲覧・送信・返信・アーカイブ、WIB締切の閲覧
- FastAPI / Application Service: WorkInBox の業務ロジック
- Thunderbird Extension: タグ定義、WIB画面の起動、Message-ID から元メール / Conversation を開く等の Thunderbird 固有操作

### v0.2 では行わないもの

- CalDAV
- Thunderbird から SQLite への締切逆同期
- Context 単位の関連締切一覧
- 独自の汎用 TODO / プロジェクト管理

---

## ドキュメント更新ルール

新しい設計文書を追加した場合は、この `docs/README.md` に必ずリンクと用途を追加する。

既存仕様を変更した場合は、関連する正式設計 (`design_workflow.md` / `design_v0_2.md`) と詳細文書の整合も確認する。

開発依頼・レビュー依頼では、原則として次のように指示できる状態を維持する。

> `docs/README.md` を起点に関連設計を確認して実装してください。
