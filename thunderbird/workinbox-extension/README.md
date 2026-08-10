# WorkInBox Thunderbird Connector

WorkInBox の Thunderbird 側 UI を担当する MailExtension の初期実装です。

現段階では、タグ導入前バックアップ・12タグ登録・タグ定義の復元に加えて、WorkInBox Web UI との Message-ID Bridge と Archive indexing policy の PoC を扱います。

業務ロジックは持ちません。IMAP メール本文や WorkInBox の SQLite を正本として管理する機能もありません。

## 対応 Thunderbird

現在の manifest は Thunderbird 140 以上を対象にしています。

利用する主な標準 API:

- `messages.tags.list()`
- `messages.tags.create()`
- `messages.tags.update()`
- `messages.tags.delete()`
- `messages.query({ headerMessageId })`
- `messageDisplay.open()`
- `folders.query()` / `folders.get()`
- `storage.local`
- `downloads.download()`

Archive の Gloda indexing ON / OFF だけは標準 MailExtension API にないため、最小の Experiment API `glodaIndexing` に閉じ込めています。

## 開発中の読み込み方法

1. リポジトリを `git pull` する。
2. Thunderbird の Add-ons Debugging を開く。
3. `Load Temporary Add-on...` を選ぶ。
4. `thunderbird/workinbox-extension/manifest.json` を選択する。
5. Thunderbird ツールバーの WorkInBox ボタンを開く。

manifest / Experiment API を変更した場合は、単なる popup の再表示ではなく Temporary Add-on 自体を Reload してください。

## WorkInBox Web UI / Message-ID Bridge

Extension の `WorkInBox を開く` から `http://127.0.0.1:8000/` を Thunderbird タブで開きます。

WorkInBox Web UI の `Thunderbirdで開く` は Message-ID を content script から background へ渡し、Thunderbird の `messages.query({ headerMessageId })` で該当メッセージを解決して通常の message display で開きます。

## Archive indexing policy PoC

Archive 配下では、Thunderbird の Favorite 状態を Global Search / Gloda の索引対象選択として使います。

```text
Favorite ON  -> Gloda indexing ON
Favorite OFF -> Gloda indexing OFF
```

WorkInBox popup の `Archive indexing policy` で次の順に操作します。

1. `Favorite と索引設定を確認` を押す。
2. Archive 配下の各フォルダについて、Favorite と現在の Gloda indexing の状態、変更予定を確認する。
3. 内容が正しければ `現在の Favorite 状態と索引設定を同期` を押す。
4. 確認ダイアログに同意した場合だけ変更を適用する。

初期 PoC では Favorite 変更への自動追随は行いません。必要なときに手動同期します。

索引を OFF にした場合、Gloda はそのフォルダの既存索引を削除対象にします。OFF から ON に戻すと再索引が始まる場合があります。そのため大量の Archive を一度に ON に戻す操作には注意してください。

実装の責務は分離しています。

- Archive / Favorite の列挙: 標準 `folders` API
- 現在の indexing 状態確認: `glodaIndexing.getStatus()`
- indexing ON / OFF: `glodaIndexing.setEnabled()`
- Gloda 内部 API へのアクセス: `experiments/gloda_indexing/implementation.js` のみ

Experiment 層は WorkInBox の業務ロジックを持ちません。

## 最初に行うこと（タグ）

### 1. 現在のタグを確認する

ポップアップ下部の「現在のタグを表示」を開くと、Thunderbird が現在認識しているタグ定義を JSON 形式で確認できます。

以前の相互運用テストで `wib-deadline` が残っている場合も表示されます。

### 2. 導入前スナップショットを保存する

`導入前スナップショットを保存` を押します。

保存する内容:

- key
- 表示名
- 色
- ordinal
- 保存日時
- 取得できる場合は Thunderbird バージョン

スナップショットは Extension の `storage.local` に一度だけ保存します。

**既存スナップショットを自動上書きしません。**

現在すでに既知の WIB タグが存在する場合は確認ダイアログを出します。そのタグも「導入前状態」として残したい場合だけ続行してください。

相互運用テスト用 `wib-deadline` を本来の導入前状態へ含めたくない場合は、スナップショット作成前に Thunderbird のタグ定義から削除してください。

### 3. JSON を外部保存する

`JSONを書き出す` を押します。

保存ファイル名:

```text
thunderbird-tags-before-workinbox.json
```

Extension を削除しても復元材料が残るよう、この JSON は通常ファイルとして別途保管してください。

必要であれば Thunderbird プロファイル全体も別途バックアップしてください。

## 12個の WIB タグを登録する

導入前スナップショットが存在する場合だけ、`12個のWIBタグを登録` が有効になります。

登録するタグ:

| key | 表示名 | 色 |
| --- | --- | --- |
| `wib-important` | `重要` | `#7B1FA2` |
| `wib-deadline` | `締切あり` | `#D32F2F` |
| `wib-schedule` | `スケジュール調整` | `#F57C00` |
| `wib-answer` | `回答必要` | `#1976D2` |
| `wib-review` | `読む・検討` | `#039BE5` |
| `wib-pending` | `判定保留` | `#757575` |
| `wib-deadline-done` | `締切登録済み` | `#8E2424` |
| `wib-schedule-done` | `スケジュール対応済み` | `#A65300` |
| `wib-waiting-reply` | `返信待ち` | `#388E3C` |
| `wib-waiting-action` | `対応待ち` | `#7CB342` |
| `wib-requested` | `依頼済み` | `#795548` |
| `wib-batch` | `一括処理` | `#424242` |

同じ key がすでに存在する場合は重複作成せず、表示名と色を WIB 定義へ合わせます。

既存の WorkInBox 管理外タグは削除しません。

## 復元

復元方法は2つあります。

### 保存済みスナップショットから復元

`保存済みスナップショットから復元` を押します。

### JSON から復元

`JSONから復元` を押し、以前書き出したバックアップ JSON を選択します。

復元処理は次を行います。

1. 現在存在する12個の既知 WIB タグ定義を削除する。
2. バックアップに記録されているタグを、同じ key / 表示名 / 色 / ordinal へ戻す。
3. バックアップ後に利用者が新しく作った WorkInBox 管理外タグは削除しない。

## 復元で行わないこと

**メール自体に保存されている `wib-*` IMAP keyword は削除しません。**

Thunderbird のタグ定義と、メールに保存された IMAP keyword は別です。

メール上の `wib-*` keyword を一括削除する機能は、影響範囲が大きいためこの初期実装には含めていません。完全アンインストール機能を実装するときに、対象 mailbox と keyword を明示した安全な操作として追加します。

## 既存の `重要` について

既存 Thunderbird の `重要` タグを `wib-important` へ自動移行する処理はまだありません。

現在の `重要` の key を確認し、既存 key を利用するか `wib-important` へ移行するかを決めるまでは、既存タグを自動変更しません。

## 現段階でこの Extension がしないこと

- メールへ自動的に WIB タグを付けない。
- メールから IMAP keyword を削除しない。
- AI 分類を行わない。
- WorkInBox の業務状態を保持しない。
- SQLite を直接操作しない。
- Thunderbird からメールを自動送信しない。
- Favorite 変更を常時監視して Gloda 設定へ自動追随しない。
