# WorkInBox Documentation Guide

このファイルを `docs/` 配下の設計文書の**入口**とする。

開発・設計を行う際は、まずこのファイルから関連文書を辿る。

実機テストを再開するときは、最初に [実機テスト再開手順](manual_test_runbook.md) だけを上から順に読む。

## 開発時の読み方

原則として次の順序で読む。

1. [開発のお約束](development_working_agreement.md)
2. [現在の作業状態](current_work.md)
3. [正式設計](design.md)
4. 作業対象に対応する詳細設計
5. 必要に応じて [Decision Log](decision_log.md) で判断の経緯を確認する
6. [ロードマップ](roadmap.md) で中長期の実装順序を確認する

チャット引き継ぎ時は [chat_handoff.md](chat_handoff.md) の手順に従う。

文書間に矛盾がある場合は、次の優先順位で扱う。

1. `design.md` の確定済み現行設計
2. 機能別の詳細設計
3. `decision_log.md` の履歴（正式設計へ未統合の Decision がある場合を除く）
4. 古いバージョンの設計・検証記録

`roadmap.md` は中長期の実装順序の資料であり、現在の進捗や業務仕様の正本にはしない。現在状態は GitHub / git と `current_work.md` を確認し、正式設計と矛盾する場合は `design.md` を優先する。

---

## 中核ドキュメント

### [development_working_agreement.md](development_working_agreement.md)

WorkInBox の仕様検討と実装を速く進めるための共通ルール。

- 仕様を `今決める / 実装時に決める / 将来でよい` の 3 段階に分ける
- 小さな設計判断はまず Decision として短く記録する
- 仕様完成度 70% を目安に最小実装へ進み、Thunderbird + WIB の実機確認で修正する

### [decision_log.md](decision_log.md)

設計相談で確定した Decision の履歴。

Decision は一定数まとまった時点または実装前に `design.md` へ統合する。統合後も判断経緯として残す。

### [design.md](design.md)

WorkInBox の**正式な現行設計**。状態遷移、タグ、通常ワークフロー、専用ワークフロー、Record、締切、TriageBox / TrackingBox / WIB / Thunderbird の責務分担を定義する。

現在の主な整理:

- WIB ダッシュボードを仕事の出発点とする。
- 利用者が新たに着眼するメールを決め、スターを付ける。
- TriageBox は未読メールを TrackingBox より先に処理し、relation と決定的な状態遷移を担当する。
- TrackingBox はスター付きメールの意味分類と再判定を担当する。
- 通常ワークフローは `返信必要` / `見る・検討` / `注目`。`何もしなくてよい` は分類結果として `一括処理 + ☆` へ進む。
- 通常ワークフローは利用者が着眼点のメールを閲覧して終了を判断し、「通常終了」または「Record に保存して終了」へ進む。
- 専用ワークフローは `締切あり` / `スケジュール調整`。WIB で進め、利用者が完了または非該当として解除して終了する。
- スケジュール支援者への依頼は `対応待ち`、支援者から返信が来たら `対応あり` とする。
- 専用ワークフローのメール relation では `X-WorkInBox-Origin-Message-ID`、標準の `In-Reply-To` / `References`、SQLite relation を役割分担して使う。
- Record は通常ワークフロー共通の保存出口とし、Message-ID で元メールを参照する。
- 正式締切は SQLite を正本とし、Message-ID で元メールを参照する。
- AI 判定前に引用された過去メール部分を機械的に除去してから文字数上限を適用する。

### [current_work.md](current_work.md)

現在の作業位置、完了済み作業、残作業、中断理由、GitHub / git の状態を記録する引き継ぎ用文書。

`作業中断` 時に更新し、`作業再開` 時に最初に確認する。

### [chat_handoff.md](chat_handoff.md)

チャット上限や担当交代時に、新しいチャット・新しい作業者へ引き継ぐための固定手順。

現在状態そのものは `current_work.md` を参照するため、通常は頻繁に書き換えない。

### [roadmap.md](roadmap.md)

中長期の実装順序と方向性を確認するための資料。

現在の進捗状態は GitHub / git と `current_work.md` を優先し、仕様判断は `design.md` を優先する。

---

## 機能別詳細

### [ai_initial_classification.md](ai_initial_classification.md)

AI 初期分類の判定順序、出力、再現率重視の考え方、`判定保留` の条件。

正式設計と矛盾する場合は `design.md` を優先する。

### [triagebox_decision_flow.md](triagebox_decision_flow.md)

TriageBox のヘッダ解析、自己送信判定、返信関係、`返信待ち` / `対応待ち` の追跡、AI 広告判定の実行条件をまとめた詳細設計。

主な関係判定:

- `From` 等による自分発メール判定
- `X-WorkInBox-Origin-Message-ID` による専用ワークフローの起点 relation
- `In-Reply-To` / `References` による標準メールスレッド判定
- SQLite relation による永続的な関係解決

正式設計と矛盾する場合は `design.md` を優先する。

### [deadline_workflow.md](deadline_workflow.md)

締切候補、正式登録、候補0件時の利用者判断、専用ワークフロー終了後の共通遷移、元メール参照をまとめた現行詳細設計。

### [thunderbird_bridge.md](thunderbird_bridge.md)

WIB と Thunderbird Extension のブリッジ設計。

通常ワークフローでは Thunderbird のメール閲覧・処理を利用し、専用ワークフローでは WIB の文脈から Thunderbird の本文作成・送信機能へ接続する。

Message-ID で対象メールを解決する共通基盤を扱う。

### [extension_dashboard_proposal.md](extension_dashboard_proposal.md)

WIBサーバーへ接続できない場合もThunderbird上で通常メール作業を継続するための、Extension内ダッシュボード検討メモ。

Thunderbird由来の現在値、WIBの接続状態、オフライン時に利用可能な操作、APIとキャッシュの候補仕様を整理する。確定済みの正式設計ではなく、実装前に `design.md` と `thunderbird_bridge.md` へ統合する。

### [design_notes_tags_and_external_intake.md](design_notes_tags_and_external_intake.md)

Thunderbird タグ、Extension、自分宛て備忘メール、ICS、将来の外部形式等に関する補足設計。

### [workinbox_components_and_waiting_review_2026-08-13.md](workinbox_components_and_waiting_review_2026-08-13.md)

3 構成要素、Thunderbird との責務分担、`判定保留`、`返信待ち` の判定・再評価・定期レビューをまとめた設計ノート。

### [thunderbird_tag_backup_restore.md](thunderbird_tag_backup_restore.md)

Thunderbird タグ定義のバックアップ/復元に関する運用資料。

---

## 履歴・検証資料

### [deadline_support_discussion_2026-08-10.md](deadline_support_discussion_2026-08-10.md)

2026-08-10 時点の締切登録支援の設計議論記録。現在仕様ではなく、現行の締切詳細設計は `deadline_workflow.md` を参照する。

### [design_v0_2.md](design_v0_2.md)

v0.2 時点の技術設計記録。現在仕様ではなく、過去の判断を確認する資料として扱う。

### [design_v0_1.md](design_v0_1.md)

v0.1 の設計記録。

### [tag_test.md](tag_test.md)

Thunderbird / IMAP タグ相互運用の検証記録。

---

## 現在の重要なアーキテクチャ判断

### 正本

- メール本体: メールサーバ
- WorkInBox 作業タグ: IMAP keyword
- WorkInBox 内部状態・relation・専用ワークフロー状態・Record: SQLite
- 正式締切: SQLite
- Thunderbird 向け締切: SQLite から生成する read-only `.ics` / VTODO

### Thunderbird との境界

- 通常ワークフローのメール閲覧・処理: Thunderbird
- 専用ワークフローの進行・メール閲覧: WIB
- メール本文作成・送信・返信・転送・アーカイブ: Thunderbird の機能
- Thunderbird Extension: Thunderbird 固有操作と WIB との接続

### 元メール参照

- active メールは INBOX を Message-ID で検索する。
- Record / 締切の元メールは INBOX、次に元メールの送信年月に対応する Archive フォルダを検索する。
- 任意のフォルダをアカウント全体から広域探索することを通常経路にはしない。

---

## ドキュメント更新ルール

新しい設計文書を追加した場合は、この `docs/README.md` にリンクと用途を追加する。

既存仕様を変更した場合は、必要な Decision を `decision_log.md` に残し、まとまった時点で `design.md` へ統合する。

開発依頼・レビュー依頼では、原則として次のように指示できる状態を維持する。

> `docs/README.md` を起点に関連設計を確認して実装してください。
