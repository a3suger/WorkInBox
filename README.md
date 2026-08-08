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

## 実行

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

同期処理の業務ロジックは `SynchronizationService` に分離されており、CLI は Application Service を呼び出す入口として動作します。将来の FastAPI UI からも同じサービスを利用する前提です。

正常に同期できると、例として次のようなログが表示されます。

```text
INFO Connecting IMAP server
INFO Checked ... existing messages
INFO Found ... flagged messages
INFO Added ... messages
INFO Reactivated ... messages
INFO Inactivated ... messages
INFO Synchronization completed
```

## PyCharm から実行する

### Python Interpreter

PyCharm の Project Interpreter には、このプロジェクト用に作成した `.venv` の Python を指定します。

例:

```text
<WorkInBox>/.venv/bin/python
```

### Run/Debug Configuration

PyCharm の `Run` → `Edit Configurations...` から Python の実行構成を作成します。

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

`Working directory` は `pyproject.toml`、`config.yaml`、`src` があるリポジトリ直下を指定します。

通常同期の設定は、ターミナルで次を実行するのと同じです。

```bash
python -m workinbox.main --config config.yaml
```

`No module named workinbox` と表示された場合は、PyCharm が使っている同じ venv で次を実行してください。

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

特に v0.2 の追跡・同期仕様は `docs/design_v0_2.md`、
メール処理全体の考え方は `docs/design_workflow.md` にまとめています。
