# WorkInBox 開発ロードマップ

## 方針

WorkInBox は Thunderbird を置き換えるメールクライアントではなく、メールから発生する仕事を整理するための業務支援システムである。

メール本文はメールサーバを正本、WorkInBox の内部状態と正式締切は SQLite を正本、作業タグは IMAP keyword を正本とする。

締切は SQLite に正式登録し、Thunderbird には SQLite から生成した読み取り専用 `.ics` / VTODO を購読させる。

CalDAV と双方向編集は v0.2 の対象外とする。

---

## v0.1 — メール追跡基盤【完了】

- IMAP 接続
- スター付きメール探索
- SQLite へのメール情報保存
- 管理対象メールの継続追跡
- スター解除・移動検出

---

## v0.2 — TrackingBox MVP

v0.2 では TrackingBox の主要フローを一通り成立させる。

### 1. 追跡状態 DB 基盤【完了】

- active / inactive 状態
- Message-ID による論理同一メール判定
- IMAP UID / UIDVALIDITY による操作対象識別

### 2. IMAP sync【完了】

- active メールの状態確認
- inactive 化
- 再アクティブ化

### 3. 新規探索 lookback N【完了】

- 新規取り込みのみ過去 N 日に制限
- 既存管理メールは N 日を超えても追跡継続

### 4. Application Service normal / full recheck【完了】

- 通常同期
- 全件再確認
- UI から再利用できる業務層

### 5. FastAPI + Jinja2 Web UI 基盤【完了】

- active / inactive 一覧
- 同期操作
- 将来機能を追加できる画面構成

### 6. IMAP Work Tag 読み書き【完了】

- WorkInBox タグ定義
- Thunderbird とのタグ相互運用
- `重要` を含むタグ体系

### 7. AI 初期分類【完了】

- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`
- 例外的な `判定保留`

`締切あり` / `スケジュール調整` / `回答必要` は再現率を重視する。

### 8. 判定保留 UI【完了】

- `判定保留` 一覧
- 利用者による再分類
- IMAP タグへの反映

### 8.5. Thunderbird Bridge【完了】

WorkInBox Web UI と Thunderbird Extension の間に、Thunderbird 固有操作のための共通ブリッジを作る。

実機 PoC で確認済み:

- Extension からローカルの WorkInBox Web UI を Thunderbird の content tab で開ける。
- WorkInBox Web UI から Message-ID を Extension へ渡せる。
- Extension が Message-ID から Thunderbird 内の元メールを解決できる。
- 元メールを通常の message display で単体表示できる。
- Gloda / Global Search / Conversation の状態に依存せず、元メールを開く経路が成立する。
- Archive 配下の Favorite 状態を列挙し、Gloda indexing の変更予定をプレビューできる。
- Favorite ON = indexing ON、Favorite OFF = indexing OFF のポリシーを手動同期できる。

Conversation / スレッド表示への直接遷移も試行したが、実機で安定して動作しなかったため元メール単体表示へ戻した。Conversation 表示は v0.2 の必須成功条件とせず、将来の追加機能として分離して扱う。

Archive Favorite の indexing 同期は、初期実装では利用者が明示的に実行する手動同期とする。Favorite 状態変更への自動追随は将来検討とする。

この Bridge は締切候補、正式締切、判定保留、スケジュール調整、返信待ち / 対応待ち等から共通利用する。

詳細は `docs/thunderbird_bridge.md` を参照する。

### 9a. 締切登録支援【未実装】

対象:

- `締切あり`
- `締切登録済み` なし

主な機能:

- AI が 0〜複数の締切候補を抽出
- 同一メールの複数締切対応
- 日付未取得候補を残す
- AI 推定確信度が低い場合の `要確認`
- 候補ごとの `登録しない / 修正する / 登録する`
- 利用者主導の `＋ 締切を追加`
- 作業中候補の SQLite 保存
- 正式締切の SQLite 保存
- Message-ID との関連保存
- 全候補の判断完了時に `締切登録済み` を自動付与
- 全候補却下時は `締切あり` を削除
- SQLite から read-only `.ics` / VTODO を生成
- Thunderbird から ICS 購読
- 候補・正式締切から Thunderbird Bridge で元メールを開く

正式締切は SQLite が正本である。

各 VTODO の UID は SQLite の deadline id から安定生成する。

詳細は `docs/deadline_support_discussion_2026-08-10.md` を参照する。

### 9b. スケジュール調整支援【未実装】

対象:

- `スケジュール調整`
- `スケジュール対応済み` なし

主な機能:

- 利用者自身で対応するフロー
- 支援者への依頼メール作成支援
- 元メールへの `依頼済み`
- 依頼メールへのスター + `対応待ち`
- 回答・反映完了後の `スケジュール対応済み`

### 10. 特殊処理後の AI 提案【未実装】

締切登録支援とスケジュール調整支援が必要な場合は、それらがすべて完了した後に一度だけ AI が次処理を提案する。

主な候補:

- `回答必要`
- `一括処理`

AI は自動確定せず、利用者が最終決定する。

### v0.2 到達状態

スター付きメールについて、

- AI で初期分類できる
- 判定保留を人間が解消できる
- WorkInBox から Message-ID を使って Thunderbird の元メールを開ける
- 締切を SQLite に正式登録できる
- Thunderbird で締切を read-only ICS として確認できる
- スケジュール調整の特殊処理を完了できる
- 特殊処理後に次の作業へ遷移できる

状態を目指す。

---

## v0.2 以後 — 関連締切 / Context

v0.2 の締切関連は Message-ID 単位とする。

後続バージョンで、`In-Reply-To` / `References` 等を利用したメールスレッド・関連 Context を検討する。

候補機能:

- 同じ Context のメールをまとめる
- Context に属する締切一覧
- 新しいメールから同じ Context へ締切追加
- 人間による関連修正

件名だけを Context の識別キーにはしない。

---

## v0.3 以後 — 待機状態 / TriageBox

- `返信待ち`
- `対応待ち`
- 催促対象
- 新着返信判定
- 元メールから新しいメールへの着目点移動
- 自分宛て備忘メールの入口判定

---

## ダッシュボード

将来、現在抱えている仕事を集約表示する。

候補:

- 判定保留
- 未処理の締切あり
- 正式締切の 7 日以内 / 今日
- 未処理のスケジュール調整
- 回答必要
- 読む・検討
- 返信待ち
- 対応待ち

締切件数は IMAP タグだけでなく SQLite の正式締切を基準に表示する。

---

## 運用安定化

- 定期実行
- 同期エラー処理
- IMAP 再接続
- AI 判定失敗時の扱い
- 操作ログ
- 重複処理防止
- 冪等性
- SQLite バックアップ
- パフォーマンス改善

---

## 将来検討: CalDAV / 双方向編集

v0.2 では Thunderbird は読み取り専用 `.ics` を購読する。

将来、Thunderbird から締切日時変更・完了操作を行い WorkInBox に反映する必要が明確になった場合に、CalDAV 等を検討する。

その時点で競合解決、複数 PC、SQLite との同期規則を設計する。
