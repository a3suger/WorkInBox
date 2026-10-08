# macOSでWIBを常駐運用する

desktop上のWIB WebをmacOSのLaunchAgentとして動かし、noteからSSHで起動、停止、更新するための手順。

LaunchAgentはdesktopへ利用者がログインしている間に動作する。ログイン前から動かすLaunchDaemonは対象外。

## 1. 初回設定

desktopでリポジトリを最新にし、実行権限を設定する。

```bash
cd /path/to/WorkInBox
chmod +x scripts/wib
mkdir -p ~/.config/workinbox
cp deploy/macos/maintenance.conf.example ~/.config/workinbox/maintenance.conf
```

`~/.config/workinbox/maintenance.conf`を開き、desktop上の実際の4つのパスを記入する。

```ini
[workinbox]
project_dir = /実際の/WorkInBox
python = /実際の/WorkInBox/.venv/bin/python
config = /実際の/WorkInBox/config.yaml
log_dir = /実際の/WorkInBox/logs
host = 127.0.0.1
port = 8000
```

このファイルはdesktop固有であり、GitHubへcommitしない。

## 2. macOSへ登録する

desktopへGUIログインした状態で実行する。

```bash
./scripts/wib install
./scripts/wib status
```

`install`は非公開設定を読み、次の実機用ファイルを自動生成してmacOSへ登録する。

```text
~/Library/LaunchAgents/jp.workinbox.web.plist
```

以後、desktopへのログイン時にWIBが自動起動する。PyCharmや起動用ターミナルを開いておく必要はない。

## 3. SSHから操作する

noteからdesktopへSSH接続し、リポジトリへ移動して操作する。

```bash
./scripts/wib status
./scripts/wib start
./scripts/wib stop
./scripts/wib restart
./scripts/wib logs
./scripts/wib logs --follow
```

`status`はLaunchAgentの登録状態に加えて、WIBの`/api/health`へ接続できるか確認する。

## 4. GitHubから更新する

```bash
./scripts/wib update
```

次の順に実行する。

1. 未commitの変更がないことを確認する
2. WIBを停止する
3. `git pull --ff-only`で更新する
4. LaunchAgent設定を再生成してWIBを起動する

未commitの変更がある場合は停止も更新もしない。`git pull`に失敗した場合は、安全のためWIBを停止したままにする。エラーを解消してから`./scripts/wib start`を実行する。

Python依存関係が変更された更新では、更新後に別途次を実行してから再起動する。

```bash
.venv/bin/python -m pip install -e .
./scripts/wib restart
```

## 5. ログ

既定では非公開設定の`log_dir`に保存する。

```text
web-launchd.log
web-launchd-error.log
```

IMAP password、API token、SSH鍵などのcredentialは管理設定、plist、ログへ記載しない。

## 6. 実機確認

- [ ] `install`後に`status`が「稼働中」となる
- [ ] noteのブラウザからSSH tunnel経由でダッシュボードを表示できる
- [ ] SSH接続を終了してもダッシュボードを表示できる
- [ ] `stop`後に接続できなくなる
- [ ] `start`後に再接続できる
- [ ] `restart`後に再接続できる
- [ ] `logs`でWIBの起動ログを確認できる
- [ ] cleanな作業ツリーで`update`が成功する
- [ ] 未commit変更がある場合、`update`がWIBを停止せずに中止する

