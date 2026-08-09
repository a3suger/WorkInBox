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
WorkInBox 側で追跡状態を管理します。
作業タグは IMAP を正本とし、未分類の active メールは通常同期後にローカル Ollama で初期分類します。

## 開発環境

### 必要なもの

- Python 3.14 以上
- Git
- IMAP 接続可能なメールアカウント
- Ollama
- `qwen2.5:7b` モデル
- PyCharm は任意ですが、ローカル開発環境として利用できます

Python のバージョンは次で確認できます。

```bash
python --version
```

Ollama をインストール後、モデルを用意します。

```bash
ollama pull qwen2.5:7b
```

Ollama のローカル API は既定で `http://127.0.0.1:11434` を使用します。

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

ai:
  url: http://127.0.0.1:11434
  model: qwen2.5:7b
  body_max_chars: 4000
  timeout_seconds: 120
```

各項目の意味:

- `host`: IMAP サーバー名。`https://` や `imap://` は付けず、ホスト名だけを書く
- `port`: IMAP SSL のポート。通常は `993`
- `username`: IMAP のユーザー名
- `password`: IMAP のパスワード
- `mailbox`: 対象 mailbox。現在は通常 `INBOX`
- `new_mail_lookback_days`: 新規メール探索の対象日数。今日を含む N 暦日を対象とする
- `database.path`: SQLite データベースの保存先
- `ai.url`: Ollama API のベース URL
- `ai.model`: 初期分類に使用する Ollama モデル
- `ai.body_max_chars`: AI へ渡す本文の最大文字数。本文先頭から切り出す
- `ai.timeout_seconds`: 1メールあたりの Ollama API タイムアウト秒数

`ai` セクションを省略した場合は、`qwen2.5:7b`、本文 4000 文字、タイムアウト 120 秒を使用します。

`config.yaml` には認証情報が入るため、Git にコミットしないでください。
このリポジトリでは `config.yaml` は `.gitignore` の対象です。

## CLI で同期する

venv を有効にした状態で、リポジトリ直下から実行します。

### 通常同期

通常同期では、SQLite 上の `active` メールを既存確認対象にし、あわせて新規のスター付きメールを探索します。

同期完了後、active メールのうち `締切あり` / `スケジュール調整` / `回答必要` / `読む・検討` / `判定保留` のいずれも付いていないメールを Ollama で自動分類し、結果を IMAP タグへ反映します。

```bash
python -m workinbox.main --config config.yaml
```

editable install 後は、次のコマンドでも実行できます。

```bash
workinbox --config config.yaml
```

Ollama が停止している、タイムアウトする、JSON が不正などの AI エラーは IMAP 同期エラーと分離されます。対象メールは未分類のまま残り、次回の通常同期で再試行されます。

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

全件再確認では AI 初期分類を自動実行しません。
同期処理の業務ロジックは `SynchronizationService` に分離されており、CLI と Web UI は同じ Application Service を利用します。

## AI 初期分類

AI へ渡す情報は、件名・差出人・宛先・本文先頭 `ai.body_max_chars` 文字です。添付ファイル自体は v0.2 では渡しません。

分類結果は Ollama の Structured Outputs を使った JSON とし、Python 側でも型と許可されるタグ組み合わせを確認します。

分類の優先順は次のとおりです。

1. `締切あり`
2. `スケジュール調整`（`締切あり` と重複可）
3. `回答必要`
4. `読む・検討`
5. 分類材料そのものが不足するときだけ `判定保留`

`締切あり`、`スケジュール調整`、`回答必要` は見逃しを減らすため再現率を重視します。

詳細は [`docs/ai_initial_classification.md`](docs/ai_initial_classification.md) を参照してください。

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
- 現在の WorkInBox IMAP タグの表示
- WorkInBox タグの手動付与・解除
- 通常同期
- 全件再確認
- 通常同期後の AI 初期分類件数と AI 分類エラーの確認

ホストやポートを変更する場合:

```bash
workinbox-web --config config.yaml --host 127.0.0.1 --port 8080
```

## Thunderbird タグの IMAP FLAGS を確認する

Thunderbird の表示タグと IMAP keyword の対応を診断する読み取り専用コマンドがあります。

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
  wib-deadline
```

このコマンドは mailbox を読み取り専用で開き、指定 UID の `FLAGS` を取得するだけで、タグやメール状態を書き換えません。

詳細な検証記録は [`docs/tag_test.md`](docs/tag_test.md) を参照してください。

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
- 通常同期後に未分類 active メールだけが AI 分類される
- 既に初期分類タグがあるメールは再分類されない
- Ollama エラー時にも IMAP 同期結果は維持される

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

作業タグは SQLite を正本にせず、IMAP 上の keyword を正本とします。

`data/` も `.gitignore` の対象で、ローカルの SQLite データはリポジトリへコミットしません。

## 設計資料

設計の詳細は `docs/` 以下を参照してください。

- `docs/design_v0_2.md`: v0.2 の追跡・同期・Web UI 仕様
- `docs/design_workflow.md`: メール処理全体の考え方
- `docs/tag_test.md`: Thunderbird タグと IMAP keyword の確認手順
- `docs/ai_initial_classification.md`: Ollama による AI 初期分類の仕様とプロンプト原則
