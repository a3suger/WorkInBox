# WorkInBox

WorkInBox は、メールやコミュニケーションツールから発生する仕事を整理し、
現在抱えている仕事を見える化するためのツールです。

## 背景

大学教員や研究者の仕事は、

- メール
- Microsoft Teams
- Slack
- 学内システム

など、さまざまな経路から発生します。

従来のタスク管理ツールでは、利用者が手動でタスクを登録する必要があります。
しかし実際には、

「メールを読んで、さらにタスク管理ツールへ転記する」

という作業が大きな負担になります。

## WorkInBox の考え方

WorkInBox はタスクを登録するツールではありません。

既存のコミュニケーションの中から仕事を発見し、整理し、見える化します。
元のメールやメッセージを正本として扱います。

現在は Thunderbird でスターを付けた IMAP メールを SQLite に同期し、
WorkInBox 側で追跡状態を管理する基盤を開発しています。

## 開発環境

### 必要なもの

- Python 3.14 以上
- Git
- IMAP 接続可能なメールアカウント
- PyCharm は任意ですが、ローカル開発環境として利用できます

Python のバージョンは次で確認できます。

```bash
python --version
```

## セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/a3suger/WorkInBox.git
cd WorkInBox
```

### 2. venv を作成

macOS / Linux の例:

```bash
python -m venv .venv
source .venv/bin/activate
```

有効になると、ターミナルの先頭に `(.venv)` などと表示されます。

### 3. WorkInBox を開発用インストール

リポジトリ直下で実行します。

```bash
python -m pip install -e .
```

これにより `src/workinbox` を編集した内容が、そのまま現在の仮想環境から利用できます。
FastAPI / Jinja2 / Uvicorn などの必要な依存パッケージも同時にインストールされます。

既に venv を作成済みの場合も、`pyproject.toml` の依存関係やコマンドが更新された後は同じコマンドを再実行してください。

## 設定ファイル

`config.example.yaml` をコピーして `config.yaml` を作成します。

```bash
cp config.example.yaml config.yaml
```

例:

```yaml
imap:
  host: mail.example.jp
  port: 993
  username: user@example.jp
  password: secret
  mailbox: INBOX
  new_mail_lookback_days: 7

database:
  path: data/workinbox.db
```

各項目の意味:

- `host`: IMAP サーバー名。`https://` や `imap://` は付けず、ホスト名だけを書く
- `port`: IMAP SSL のポート。通常は `993`
- `username`: IMAP のユーザー名
- `password`: IMAP のパスワード
- `mailbox`: 対象 mailbox。現在は通常 `INBOX`
- `new_mail_lookback_days`: 新規メール探索の対象日数。今日を含む N 暦日を対象とする
- `database.path`: SQLite データベースの保存先

`config.yaml` には認証情報が入るため、Git にコミットしないでください。
このリポジトリでは `config.yaml` は `.gitignore` の対象です。

## CLI で同期する

venv を有効にした状態で、リポジトリ直下から実行します。

### 通常同期

通常同期では、SQLite 上の `active` メールを既存確認対象にし、あわせて新規のスター付きメールを探索します。

```bash
python -m workinbox.main --config config.yaml
```

editable install 後は、次のコマンドでも実行できます。

```bash
workinbox --config config.yaml
```

### 全件再確認

全件再確認では、`active` に加えて `inactive_unstarred` / `inactive_moved` の既存レコードも保存済み IMAP UID で再確認します。
再びスター付きとして確認できたメールは `active` に復帰できます。

```bash
python -m workinbox.main --config config.yaml --full-recheck
```

または:

```bash
workinbox --config config.yaml --full-recheck
```

同期処理の業務ロジックは `SynchronizationService` に分離されており、CLI と Web UI は同じ Application Service を利用します。

## Web UI を起動する

FastAPI + Jinja2 のサーバーサイドHTML UIを起動します。

```bash
workinbox-web --config config.yaml
```

または:

```bash
python -m workinbox.web --config config.yaml
```

既定ではローカルホストだけにバインドします。

```text
http://127.0.0.1:8000/
```

ブラウザで開くと、次の操作ができます。

- Active メール一覧の表示
- Inactive メール一覧の表示
- 通常同期
- 全件再確認
- 同期結果とメール単位エラーの確認

現段階の Web UI は v0.2 の基盤です。IMAP 上の作業タグ読み取りは次の実装ステップのため、作業タグ欄は現在 `未取得` と表示されます。

ホストやポートを変更する場合:

```bash
workinbox-web --config config.yaml --host 127.0.0.1 --port 8080
```

## Thunderbird タグの IMAP FLAGS を確認する

ステップ6の作業タグ読み書きを実装する前に、Thunderbird の表示タグと IMAP keyword の対応を実測するための読み取り専用診断コマンドがあります。

SQLite の `emails.uid` で対象メールの UID を確認した後、次を実行します。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

または:

```bash
python -m workinbox.imap_debug --config config.yaml --uid 12345
```

出力例:

```text
Mailbox: INBOX
UIDVALIDITY: 987654
UID: 12345
FLAGS:
  \\Seen
  \\Flagged
  $label1
```

このコマンドは mailbox を読み取り専用で開き、指定 UID の `FLAGS` を取得するだけで、タグやメール状態を書き換えません。

Thunderbird でタグを付ける前、付けた後、再び外した後の3回を比較して、表示名と IMAP keyword の対応を確認してください。

詳細な手順と記録表は [`docs/tag_test.md`](docs/tag_test.md) を参照してください。

## PyCharm から実行する

### Python Interpreter

PyCharm の Project Interpreter には、このプロジェクト用に作成した `.venv` の Python を指定します。

例:

```text
<WorkInBox>/.venv/bin/python
```

### CLI の Run/Debug Configuration

通常同期の設定例:

```text
Name: WorkInBox
Run: module
Module name: workinbox.main
Script parameters: --config config.yaml
Working directory: /path/to/WorkInBox
Python interpreter: /path/to/WorkInBox/.venv/bin/python
```

全件再確認用の実行構成を別に作る場合は、`Script parameters` を次にします。

```text
--config config.yaml --full-recheck
```

### Web UI の Run/Debug Configuration

Web UI 用には別の Python 実行構成を作ると便利です。

```text
Name: WorkInBox Web
Run: module
Module name: workinbox.web
Script parameters: --config config.yaml
Working directory: /path/to/WorkInBox
Python interpreter: /path/to/WorkInBox/.venv/bin/python
```

実行後、ブラウザで次を開きます。

```text
http://127.0.0.1:8000/
```

### IMAP FLAGS 診断の Run/Debug Configuration

タグ確認用には次の構成を作れます。

```text
Name: WorkInBox IMAP Flags
Run: module
Module name: workinbox.imap_debug
Script parameters: --config config.yaml --uid 12345
Working directory: /path/to/WorkInBox
Python interpreter: /path/to/WorkInBox/.venv/bin/python
```

対象メールを変えるときは `--uid` の値だけ変更します。

`No module named workinbox` や FastAPI 関連の import error が表示された場合は、PyCharm が使っている同じ venv で次を実行してください。

```bash
python -m pip install -e .
```

## テスト

リポジトリ直下で実行します。

```bash
python -m unittest discover -s tests -v
```

コード変更後は、少なくともこのテストが通ることを確認します。

IMAP 同期を変更した場合は、自動テストに加えて実環境でも次を確認すると安全です。

- 対象期間内のスター付きメールが新規登録される
- `new_mail_lookback_days` より古い未登録メールは新規登録されない
- 既に登録済みの古いメールは追跡が継続される
- スターを外したメールが `inactive_unstarred` になる
- 対象 mailbox から移動したメールが `inactive_moved` になる
- 全件再確認で inactive メールも再確認対象になる

Web UI を変更した場合は、起動後に Active / Inactive の両画面と、通常同期 / 全件再確認の両ボタンも確認してください。

## SQLite データ

既定の設定例では SQLite データベースは次に作成されます。

```text
data/workinbox.db
```

PyCharm の Database ツールや SQLite 対応ツールを使って内容を確認できます。

追跡状態では主に次の値を使用します。

- `active`: 対象 mailbox にあり、スター付きで追跡中
- `inactive_unstarred`: mailbox にはあるが、スターが外された
- `inactive_moved`: 保存していた UID が対象 mailbox から見つからなくなった

`data/` も `.gitignore` の対象で、ローカルの SQLite データはリポジトリへコミットしません。

## 設計資料

設計の詳細は `docs/` 以下を参照してください。

- `docs/design_v0_2.md`: v0.2 の追跡・同期・Web UI 仕様
- `docs/design_workflow.md`: メール処理全体の考え方
- `docs/tag_test.md`: Thunderbird タグと IMAP keyword の確認手順
