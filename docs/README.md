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
2. 現在の全体設計
3. 機能別の詳細設計・議論メモ
4. 古いバージョンの設計・検証記録

矛盾を発見した場合は、実装側で勝手に解釈せず文書を更新して整合させる。

---

## 中核ドキュメント

### [design.md](design.md)

WorkInBox の目的、責務境界、正本の考え方などを短くまとめた全体設計。

最初に「WorkInBox が何をする/しないか」を確認するための文書。

### [design_workflow.md](design_workflow.md)

TrackingBox / TriageBox、タグ体系、締切登録支援、スケジュール調整支援、返信待ち、`見る・検討`、WIB 保存情報、元メール参照、ダッシュボードなどの**正式な業務ワークフロー**。

業務ロジックを変更する場合は必ず参照する。

現在の重要な整理:

- `見る・検討` は、元メールへの返信は不要だが内容を読み、後から残す価値があるかを判断する通常フロー。
- active な `見る・検討` の出口は原則 `WIB に保存` または `一括処理` の 2 つ。
- WIB に保存した場合、元メールはスターを外してアーカイブできるが、`見る・検討` タグを参照用に残してよい。
- Archive フォルダを選択して `見る・検討` の Quick Filter を適用すれば、保存済み元メールを Thunderbird 側からも再発見できる。
- WIB 保存情報は元メールへの Message-ID 参照、AI要約、利用者メモ等を保持し、後から検索、締切連携、元メール閲覧、返信、新規派生メール作成へつなげる。

### [roadmap.md](roadmap.md)

現在の実装状況と、次に実装する順序。

「次に何を作るか」を判断する場合はこの文書を参照する。

### [design_v0_2.md](design_v0_2.md)

v0.2 時点の技術的な境界、追跡状態、FastAPI、IMAP、SQLite、締切登録支援などの設計記録。

現在の業務ワークフローと矛盾する場合は `design_workflow.md` を優先する。

---

## 機能別詳細

### [ai_initial_classification.md](ai_initial_classification.md)

AI 初期分類の判定順序、出力、再現率重視の考え方、`判定保留` の条件。

AI 分類を変更する場合に参照する。

### [triagebox_decision_flow.md](triagebox_decision_flow.md)

TriageBox のヘッダ解析、自己送信判定、返信関係、`返信待ち` / `対応待ち` の追跡、AI 広告判定の実行条件をまとめた詳細設計。

主な内容:

- `From` が自分かを最初の分岐とする
- WIB 作成支援メールは `X-WorkInBox-Origin-Message-ID` で起点メールへ関連付ける
- 他者発メールは `In-Reply-To` / `References` から追跡中メールとの関係を解決する
- AI 広告判定は `新規受信メール` と確定したメールだけに行う
- TrackingBox / Thunderbird Extension と TriageBox の責務境界

TriageBox、返信待ち、対応待ち、広告判定を変更する場合に参照する。

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

### [thunderbird_bridge.md](thunderbird_bridge.md)

WorkInBox Web UI と Thunderbird Extension の共通ブリッジ設計。

主な内容:

- FastAPI は WorkInBox 本体/UI/APIとして独立して動かす
- Extension は Thunderbird 固有 API だけを担当する
- Message-ID から Thunderbird 内のメールを検索する
- WorkInBox の画面から元メールを開く
- 締切・判定保留・返信待ち・WIB 保存情報等で同じ仕組みを再利用する

WIB 保存情報の元メールは Archive 等へ移動している可能性があるため、正式設計では Message-ID を正本の識別子とし、保存フォルダを検索ヒントとして扱う。

### [design_notes_tags_and_external_intake.md](design_notes_tags_and_external_intake.md)

Thunderbird タグ、Extension、自分宛て備忘メール、ICS、将来の外部形式等に関する補足設計。

### [workinbox_components_and_waiting_review_2026-08-13.md](workinbox_components_and_waiting_review_2026-08-13.md)

3 構成要素、Thunderbird との責務分担、`判定保留`、`返信待ち` の判定・再評価・定期レビューをまとめた設計ノート。

正式ワークフローと矛盾する場合は `design_workflow.md` を優先する。

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
- WorkInBox 内部状態・relation・保存情報: SQLite
- 正式締切: SQLite
- Thunderbird 向け締切: SQLite から生成する read-only `.ics` / VTODO

### Thunderbird との境界

- Thunderbird: メールの閲覧・本文作成・送信・返信・転送・アーカイブ
- FastAPI / Application Service: WorkInBox の業務ロジック
- Thunderbird Extension: Thunderbird 固有操作、Message-ID からのメール表示、WIB relation 用ヘッダー付与

### 元メール参照

- active な作業メールは INBOX 前提で高速検索する。
- WIB 保存情報の元メールは Archive 等へ移動している可能性がある。
- 保存情報では Message-ID を正式な識別子とし、account と folder hint を補助情報として持つ。
- folder hint で見つからない場合は Archive 等の候補、最後に対象アカウント全体へ検索範囲を広げる。

---

## ドキュメント更新ルール

新しい設計文書を追加した場合は、この `docs/README.md` に必ずリンクと用途を追加する。

既存仕様を変更した場合は、関連する正式設計 (`design_workflow.md`) と詳細文書の整合も確認する。

開発依頼・レビュー依頼では、原則として次のように指示できる状態を維持する。

> `docs/README.md` を起点に関連設計を確認して実装してください。
