# WorkInBox v0.1 設計書

## 1. 目的

WorkInBox は、利用者が「後で対応する必要がある」と判断したメールを収集し、現在取り組むべき仕事を管理するための基盤を提供する。

Version 0.1 では Thunderbird のスター付きメールのみを対象とする。
AIによる分析、分類、締切抽出は行わない。

---

## 2. スコープ

### 2.1 対象

- Thunderbird のスター付きメール
- IMAP メールボックス
- IMAPキーワード `WIB/Tracked`
- SQLite データベース
- 期間を限定した新規メール探索
- 取り込み済みメールの継続追跡
- WorkInBoxからのスター解除
- `WIB/Tracked` を利用した復元

### 2.2 対象外

- AI分析
- メール分類
- 締切抽出
- Teams、Slack等との連携
- 通知・リマインダー
- Web UI、Electron UI
- メール削除
- メール移動・アーカイブ
- 既読・未読状態の変更
- 返信・転送・新規メール作成

---

## 3. システム構成

```mermaid
flowchart TD
    TB[Thunderbird]
    IMAP[IMAP Server]
    WIB[WorkInBox]
    DB[(SQLite)]

    TB <--> IMAP
    IMAP <--> WIB
    WIB <--> DB
```

---

## 4. 基本方針

### 4.1 タスクの手入力を要求しない

利用者は新たなタスクを手入力しない。
Thunderbirdでスターを付けることを、WorkInBoxへの仕事登録操作とする。

### 4.2 現在の仕事に専念する

WorkInBoxは、IMAP上のすべてのスター付きメールを無条件に取り込まない。
新規探索では、設定された期間内に受信したスター付きメールだけを対象とする。

一度取り込んだメールは、受信日時が探索期間外になっても、WorkInBox上での追跡が終了するまで継続して追跡する。

### 4.3 IMAPとSQLiteの役割

メール本文、ヘッダー、標準IMAPフラグおよびIMAPキーワードは、IMAPサーバ上の情報を基準とする。

WorkInBoxは、管理対象として取り込んだメールにIMAPキーワード `WIB/Tracked` を付与する。

SQLiteは、管理対象メールの表示、検索、同期状態、取得日時、操作履歴および将来の解析結果を保持するローカル台帳とする。

SQLiteが失われた場合は、IMAP上の `WIB/Tracked` を付与されたメールから管理対象を復元できるものとする。

### 4.4 限定的なIMAP書き込み

WorkInBoxは、次の変更だけをIMAPサーバへ行う。

- `WIB/Tracked` キーワードの付与
- WorkInBox上の完了操作に伴う `\Flagged` の解除

次の操作は禁止する。

- メール削除
- メール移動・アーカイブ
- 本文変更
- 既読・未読変更
- WorkInBox管理外のフラグ・タグ変更

### 4.5 メールを識別する情報

メールの論理的な識別には `Message-ID` を使用する。
IMAP上の操作には、次の組み合わせを使用する。

- mailbox
- UIDVALIDITY
- UID

UIDが無効になった場合は、`Message-ID` を用いてメールを再検索する。

---

## 5. WorkInBoxとThunderbirdの責務

### 5.1 責務分担の基本

WorkInBoxは、メールを仕事として追跡するかどうかを管理する。
Thunderbirdは、メールの閲覧、返信およびメールボックス内での整理を担当する。

WorkInBoxは、Thunderbirdの代替メールクライアントを目的としない。

### 5.2 WorkInBoxの責務

WorkInBoxは、次の処理を担当する。

- 設定期間内のスター付きメールを新規管理対象として探索する
- 新規管理対象をSQLiteへ登録する
- 新規管理対象へ `WIB/Tracked` を付与する
- 一度取り込んだメールを、期間外になっても継続追跡する
- IMAP側でスターが解除されたことを検出する
- WorkInBox上で利用者が完了としたメールのスターを解除する
- 完了した仕事を通常の仕事一覧から除外する
- 完了履歴および同期状態をSQLiteに保持する
- `WIB/Tracked` を使ってSQLiteの管理対象を復元する

### 5.3 Thunderbirdおよび利用者の責務

利用者はThunderbird上で、次の操作を行う。

- 対応が必要なメールにスターを付ける
- メールを閲覧する
- メールへ返信する
- メールを転送する
- 不要になったメールをアーカイブする
- 必要に応じてフォルダを整理する

返信したこと自体は、WorkInBox上での追跡終了を必ずしも意味しない。
返信後も追加作業や相手からの返答待ちがあり得るため、Version 0.1では返信済み状態を自動的な完了条件としない。

### 5.4 完了とスター解除

利用者がWorkInBox上で仕事を完了にした場合、WorkInBoxは対象メールのスターを解除する。

スター解除は、当該メールについてWorkInBox上での追跡を終了することを意味する。
スター解除は、メールの削除、アーカイブ、返信完了またはメールスレッド全体の終了を意味しない。

### 5.5 アーカイブの扱い

WorkInBoxは、メールのアーカイブを行わない。

スターが解除され、既読となったメールをいつアーカイブするかは、利用者のThunderbird上の運用に委ねる。
Version 0.1では、アーカイブ条件およびアーカイブ処理のワークフローを定めない。

---

## 6. 利用シナリオ

### 6.1 要対応メールの登録

利用者はThunderbirdで、後で対応する必要があるメールにスターを付ける。

### 6.2 新規取り込み

WorkInBoxを実行すると、設定期間内のスター付きメールを探索する。
未登録メールをSQLiteへ追加し、IMAP上のメールへ `WIB/Tracked` を付与する。

### 6.3 Thunderbirdでの作業

利用者はThunderbird上でメールを閲覧し、必要に応じて返信または転送する。
これらの操作だけでは、WorkInBox上の仕事を自動的に完了としない。

### 6.4 継続追跡

一度取り込んだメールは、探索期間を過ぎても追跡を継続する。

Thunderbirdなど、WorkInBox以外からスターが解除された場合は、次回同期時に完了状態として記録し、通常の一覧から除外する。

### 6.5 WorkInBoxからの完了

WorkInBoxで仕事を完了にすると、IMAP上の `\Flagged` を解除する。
IMAP更新に成功した後、SQLite上の状態を完了へ変更する。

### 6.6 アーカイブ

完了後のメールをアーカイブするかどうか、およびアーカイブする時期は利用者がThunderbird上で判断する。
WorkInBoxはアーカイブ操作へ関与しない。

### 6.7 復元

SQLiteを失った場合、IMAP上の `WIB/Tracked` 付きメールを走査して台帳を再構築する。

通常の復元対象は、`WIB/Tracked` が付いたメールとする。
タグが利用できない場合の救済手段として、指定日以降を走査する日付指定復元を将来追加できるものとする。

---

## 7. 設定ファイル

ファイル名:

```text
config.yaml
```

例:

```yaml
imap:
  host: mail.example.jp
  port: 993
  username: user@example.jp
  password: secret
  mailbox: INBOX
  tracking_keyword: WIB/Tracked
  allow_flag_updates: true
  allow_keyword_updates: true

sync:
  new_message_lookback_days: 90

database:
  path: data/workinbox.db
```

### 7.1 new_message_lookback_days

新規メールを探索する受信日の範囲を日数で指定する。
この値は新規探索にだけ適用し、すでにSQLiteへ登録されているメールの追跡には適用しない。

---

## 8. 実装環境

- Python 3.14
- macOS

標準ライブラリ:

- sqlite3
- imaplib
- email
- logging
- datetime

外部ライブラリ:

- PyYAML

---

## 9. ディレクトリ構成

```text
WorkInBox/
├── config.yaml
├── data/
│   └── workinbox.db
├── src/
│   └── workinbox/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── database.py
│       ├── imap_client.py
│       └── models.py
├── logs/
└── docs/
    └── design_v0_1.md
```

---

## 10. メール取得仕様

### 10.1 接続方式

IMAP4 over SSL

### 10.2 対象フォルダ

```text
INBOX
```

Version 0.1では、新規探索対象をINBOXに限定する。
取り込み後に利用者がアーカイブまたは移動したメールを継続追跡する方法は、今後の検討事項とする。

### 10.3 新規探索条件

```text
FLAGGED
かつ
受信日が new_message_lookback_days の範囲内
```

### 10.4 既存追跡条件

SQLiteに登録済みのメールは、受信日に関係なくIMAP上の状態を確認する。

### 10.5 復元条件

```text
KEYWORD WIB/Tracked
```

復元時にアクティブな仕事だけを戻す場合は、さらに `FLAGGED` を条件へ加える。

### 10.6 取得項目

- Message-ID
- mailbox
- UIDVALIDITY
- UID
- Subject
- From
- To
- Date
- Body
- IMAP flags
- IMAP keywords

添付ファイルは取得しない。

本文は `text/plain` を優先し、存在しない場合は `text/html` を使用する。
メール取得には、既読状態を変更しない `BODY.PEEK[]` を使用する。

---

## 11. 同期仕様

### 11.1 概要

同期処理を、次の2種類に分ける。

1. 新規探索
2. 既存追跡

同期完了後のSQLiteは、IMAP上のスター付きメール全件とは一致しない。
SQLiteのアクティブ一覧は、次の集合と一致する。

```text
期間内に新規取り込みしたスター付きメール
+
過去に取り込み済みで現在もスター付きのメール
```

### 11.2 新規メール

次の条件をすべて満たすメールを追加する。

- `\Flagged` が付いている
- 受信日が探索期間内である
- SQLiteに同じ `Message-ID` が存在しない

追加後に `WIB/Tracked` を付与する。

### 11.3 既存メール

SQLiteに登録済みのメールは、探索期間に関係なく追跡する。

確認項目:

- IMAP上にメールが存在するか
- `\Flagged` が付いているか
- UIDVALIDITYが変化していないか
- UIDが有効か

### 11.4 IMAP側でスターが解除された場合

IMAP上で `\Flagged` が解除された場合、SQLiteレコードを物理削除しない。

```text
tracking_status = completed
```

通常の仕事一覧からは除外する。

### 11.5 WorkInBox側で完了した場合

処理順序:

1. UIDを使ってIMAP上の `\Flagged` を解除する
2. IMAP更新結果を確認する
3. 成功した場合だけSQLiteを完了状態へ変更する

IMAP更新に失敗した場合、SQLite上ではアクティブ状態を維持し、エラーを記録する。

### 11.6 メールが見つからない場合

即時に完了または削除とはみなさない。

```text
tracking_status = missing
```

UIDVALIDITYおよびUIDを確認し、必要に応じて `Message-ID` で再検索する。

メールが利用者によってアーカイブまたは別フォルダへ移動された可能性も考慮し、単にINBOXから見つからないことを完了とはみなさない。

---

## 12. 復元仕様

### 12.1 通常復元

IMAP上で `WIB/Tracked` が付いたメールを全期間検索する。
取得したメールからSQLiteを再構築する。

スター付きメールは `active`、スターなしメールは `completed` として復元する。

### 12.2 日付指定復元

IMAPキーワードが利用できない場合、または緊急時の救済手段として、指定日以降のメールを走査する方式を将来提供できる。

```bash
workinbox restore --since 2026-04-01
```

日付指定復元では、過去にWorkInBoxへ取り込まれていなかったメールも候補に含まれるため、通常復元より精度が低い。

### 12.3 DBバックアップ

SQLiteには、IMAPタグだけでは復元できない同期履歴や将来の解析結果が保存される。
そのため、IMAPタグによる復元とは別に、SQLiteファイルのバックアップを推奨する。

---

## 13. データモデル

```mermaid
erDiagram
    EMAILS {
        INTEGER id
        TEXT message_id
        TEXT mailbox
        INTEGER uidvalidity
        INTEGER imap_uid
        TEXT sender
        TEXT recipients
        TEXT subject
        TEXT received_at
        TEXT body
        TEXT tracking_status
        TEXT first_imported_at
        TEXT last_checked_at
        TEXT completed_at
        TEXT synchronized_at
    }
```

`tracking_status` は次の値を取る。

- active
- completed
- missing
- error

---

## 14. データベース

SQLite を利用する。
ファイル名は `workinbox.db` とする。

```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    mailbox TEXT NOT NULL,
    uidvalidity INTEGER NOT NULL,
    imap_uid INTEGER NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT,
    subject TEXT,
    received_at TEXT,
    body TEXT,
    tracking_status TEXT NOT NULL DEFAULT 'active',
    first_imported_at TEXT NOT NULL,
    last_checked_at TEXT NOT NULL,
    completed_at TEXT,
    synchronized_at TEXT NOT NULL
);
```

---

## 15. ログ出力

標準出力へ出力する。

```text
INFO Connecting IMAP server
INFO Found 12 new flagged candidates within 90 days
INFO Added 3 messages
INFO Added WIB/Tracked to 3 messages
INFO Checked 18 tracked messages
INFO Completed 2 messages
INFO Synchronization completed
```

---

## 16. エラー処理

### 16.1 IMAP接続失敗

`ERROR IMAP connection failed` を出力して終了する。

### 16.2 SQLiteエラー

`ERROR Database error` を出力して終了する。

### 16.3 IMAPキーワード付与失敗

SQLiteへの新規登録を確定せず、エラーを記録する。

### 16.4 スター解除失敗

SQLiteを完了状態へ変更せず、アクティブ状態を維持する。

---

## 17. 完了条件

以下をすべて満たした場合、Version 0.1 は完成とする。

- IMAP接続できる
- 設定期間内の `FLAGGED` メールを取得できる
- SQLiteへ保存できる
- `Message-ID` による重複排除ができる
- mailbox、UIDVALIDITY、UIDを保存できる
- 新規取り込みメールへ `WIB/Tracked` を付与できる
- 取り込み済みメールを期間外でも追跡できる
- IMAP側のスター解除を完了状態として反映できる
- WorkInBoxからスターを解除できる
- 完了メールを通常一覧から除外できる
- `WIB/Tracked` からSQLiteを復元できる
- 返信・転送を自動完了条件にしない
- メール削除、移動、アーカイブ、既読変更を行わない
