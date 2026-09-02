# WorkInBox Thunderbird Connector

WorkInBox の Thunderbird 側 UI を担当する MailExtension の初期実装です。

現段階では、タグ導入前バックアップ・13タグ登録・タグ定義の復元に加えて、Extension内ダッシュボード、WorkInBox Web UI との Message-ID Bridge、Archive indexing policy、WIB Quick Filter 作業ビューを扱います。

業務ロジックは持ちません。IMAP メール本文や WorkInBox の SQLite を正本として管理する機能もありません。

## 対応 Thunderbird

現在の manifest は Thunderbird 140 以上を対象にしています。

利用する主な標準 API:

- `messages.tags.list()`
- `messages.tags.create()`
- `messages.tags.update()`
- `messages.tags.delete()`
- `messages.query({ headerMessageId })`
- `messages.query({ folderId })` / `messages.continueList()`
- `messageDisplay.open()`
- `accounts.list()` / `accounts.get()`
- `folders.query()` / `folders.get()`
- `mailTabs.create()` / `mailTabs.get()` / `mailTabs.update()`
- `mailTabs.setQuickFilter()`
- `tabs.update()`
- `tabs.query({ type: "tasks" })`
- `storage.local`
- `downloads.download()`

標準 MailExtension API で直接扱えない処理だけを小さな Experiment API に閉じ込めています。

- `glodaIndexing`: Archive の Gloda indexing ON / OFF
- `tabTitle`: WIB 専用メールタブの表示タイトル変更
- `imapAccounts`: 指定した Thunderbird account id の incoming server 情報読み取り
- `tasksSpace`: 既存ToDoタブがない場合にThunderbirdのToDoスペースを開く

Experiment 層に WorkInBox の業務ロジックを持たせません。

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

## Extension内ダッシュボード

popupの`ダッシュボードを開く`からThunderbird内の専用タブを開きます。専用タブは1枚だけ作成して再利用します。

ダッシュボードはWIBの`/api/health`、`/api/extension/bootstrap`、`/api/sync-status`で接続状態を確認します。WIBへ接続できた設定とThunderbird集計結果は`storage.local`へ保存し、WIB停止中やSSH tunnel切断中も対象mailboxを特定できるようにします。IMAP password、credential、メール本文は保存しません。

件数はThunderbirdのメッセージヘッダーからページ単位で集計します。未着眼は合計と未読 / 既読の内訳を表示して`new_mail_lookback_days`を適用し、通常ワークフロー、専用タグ、判定保留、待機状態はmailbox全体の`対象タグ + スター付き`を数えます。整理済みメールはmailbox全体の`一括処理（旧タグを含む）+ スターなし`を数え、アーカイブ待ちとして表示します。

WIB WebとExtensionダッシュボードの未着眼カードから開くThunderbird作業ビューにも`new_mail_lookback_days`を適用し、未読・既読を一緒に表示します。ほかの作業ビューはmailbox全体を対象にします。

WIB停止中も各カードからThunderbird作業ビューを開けます。WIB Webが必要なAI、SQLite、専用ワークフロー、Record等の導線は接続不可時に無効になります。

接続状態欄の`通常同期`はWIB接続中だけ利用できます。同期開始後は実行中表示になり、`/api/sync-status`で完了まで確認します。

正式締切の「期限超過」と「今後7日以内」は、WIBの`/api/deadlines/summary`がSQLiteから集計した値を表示します。`ThunderbirdのToDoを開く`は既存ToDoタブを再利用し、存在しない場合は`tasksSpace`でToDoスペースを開きます。

Extension `0.3.10`では、メール閲覧画面のmessage display actionを「WIB操作メニュー」の構成確認用プレビューへ変更しています。「通常フロー」と「専用フロー（締切・スケジュール調整）」を開閉して項目を確認できますが、各項目はまだタグ、スター、WIB画面を変更しません。

Extension `0.3.11`では、正式アイコンを青い線画の受信トレイと、中央の丸みのある`w`を組み合わせたデザインへ更新しました。

Extension `0.3.12`では、正式アイコンのWorkInBoxボタンをThunderbirdのスペースツールバーへ常設しました。ボタンを押すとExtension内ダッシュボードが開き、以後は同じ専用タブを再利用します。popupの`ダッシュボードを開く`も同じスペースを開きます。

Extension `0.3.13`では、重複していたメニューバーのWorkInBoxボタンを削除しました。従来のpopupはアドオンの`設定・ツール`画面として維持し、Extension内ダッシュボード右上の歯車ボタン、またはアドオンマネージャーの設定から開きます。

Extension `0.3.14`では、`設定・ツール`画面からダッシュボード、WIB Web UI、WIB作業ビューの重複導線を削除しました。この画面はArchive索引設定とWIBタグの登録・バックアップ・復元に限定します。

Extension `0.3.15`では、メール閲覧画面のWIB操作メニューから「締切登録を開始／続ける」と「スケジュール調整を開始／続ける」を利用可能にしました。選択したメールへ対応する専用タグとスターを付け、再利用する専用タブでそのメールだけのWIB画面を開きます。WIBへ接続できない場合はExtension内の接続案内と再試行ボタンを表示します。通常フローおよび専用フローの「なし」操作は引き続きプレビューです。

Extension `0.3.16`では、Thunderbirdが渡す山括弧なしのMessage-IDとWIBが保持する山括弧付きMessage-IDを同一として扱い、メール単位の専用フローが対象外と誤判定される問題を修正しました。

Extension `0.3.17`では、専用フロー選択時にメール検索とタグ更新を待ってからタブを開いていた順序を変更しました。専用タブを先に表示・フォーカスし、タブ内の準備画面でタグ更新とWIB接続確認を進めるため、操作直後に画面が切り替わります。

Extension `0.3.18`では、WIB操作メニューの「このメールには締切なし」と「スケジュール調整なし」を利用可能にしました。選択した専用タグを外し、ほかの未完了WIB作業タグが残る場合はその作業とスターを維持します。残らない場合は`一括処理`を付けてスターを外します。

Extension `0.3.23`では、WIB操作メニューを実動作へ移行しました。通常フローは回答必要・見る／検討・注目の単一選択で、選び直すと旧通常タグを外します。対応ありメールでは専用の3操作だけを表示し、追加質問、お礼後終了、返信なし終了を選べます。Record終了は自分宛ての特殊ヘッダー付き登録メールを作成し、通常同期でTriageBoxが保存、TrackingBoxが元メールを要約して完了させます。

Extension `0.3.19`では、WIB作業タブでメールを選ぶとThunderbirdがタブ名を`受信トレイ`へ戻す問題に対応しました。タイトル変更とタブ再選択を監視し、保存している`WIB:<ビュー名>`を再適用します。タブの識別自体は引き続きタブIDで行います。

Extension `0.3.20`では、同じMessage-IDのコピーが複数フォルダーにある場合に、専用フロー操作が閲覧中とは別のコピーを更新し得る問題を修正しました。メニューからThunderbird内部のメッセージIDも渡し、表示中のメールを優先してタグとスターを更新します。

Extension `0.3.21`では、標準のタブ更新イベントでは検知できなかったThunderbird内部のタブ名上書きに対応しました。`tabTitle` ExperimentがWIB作業タブのlabel属性を直接監視し、メール選択後に`受信トレイ`へ変わった場合も`WIB:<ビュー名>`へ戻します。

Extension `0.3.22`では、メール表示後のWIB作業タブが内部的に三ペインのメール一覧として操作できず、別のダッシュボードボタンを押してもビューが切り替わらない場合に対応しました。既存タブへの適用が失敗した場合だけ、そのWIB専用タブを閉じて新しいメール一覧タブを作り、選択したビューを再適用します。

## WIB Quick Filter 作業ビュー PoC

WIB の現在作業を Thunderbird のメール一覧で処理するため、専用のメールタブを 1 枚だけ作成して再利用します。

通常利用中の INBOX タブへ `mailTabs.setQuickFilter()` を適用すると、利用者が手動で設定していた Quick Filter 条件を上書きするため、WIB は通常タブを変更しません。

### 対象アカウントの自動解決

WIB 作業ビューの対象 IMAP account / mailbox は、WorkInBox 側の `config.yaml` の `imap` 設定を正本とします。

利用者が Thunderbird popup で対象アカウントを選択・保存する必要はありません。

作業ビューを開くたびに Extension は WorkInBox Web の

```text
/api/thunderbird/imap-target
```

から次の情報を取得します。

- `host`
- `port`
- `username`
- `mailbox`

IMAP password はこの API から返しません。

Extension は Thunderbird の IMAP アカウントを列挙し、`imapAccounts` Experiment で各 account の incoming server 情報を読み取って照合します。

基本照合は `host + port + username` です。username は Thunderbird と WIB config の表現差を吸収するため、完全一致に加えて、一方が `user@example.jp`、もう一方が `user` の場合はローカル部一致を候補として認めます。

一致候補が 0 件または複数件の場合は別アカウントへ自動フォールバックせずエラーにします。

アカウント解決後は `config.yaml` の `imap.mailbox` を対象フォルダとして使用します。通常は `INBOX` を想定しています。

これにより WIB config と Thunderbird Extension で対象アカウント設定を二重管理しません。

### 作業ビューの切り替え

popup とExtension内ダッシュボードから次の作業ビューを選択できます。

| 表示名 | Quick Filter 条件 | タブ名 |
| --- | --- | --- |
| 未着眼・未読 | スターなし AND 一括処理なし + 未読 | `WIB:未着眼・未読` |
| 未着眼・既読 | スターなし AND 一括処理なし | `WIB:未着眼・既読` |
| 返信必要 | `wib-answer` AND スター付き | `WIB:返信必要` |
| 締切あり | `wib-deadline` AND スター付き | `WIB:締切あり` |
| スケジュール調整 | `wib-schedule` AND スター付き | `WIB:スケジュール調整` |
| 見る・検討 | `wib-review` AND スター付き | `WIB:見る・検討` |
| 注目 | `wib-watch` AND スター付き | `WIB:注目` |
| 判定保留 | `wib-pending` AND スター付き | `WIB:判定保留` |
| 返信待ち | `wib-waiting-reply` AND スター付き | `WIB:返信待ち` |
| 対応待ち | `wib-waiting-action` AND スター付き | `WIB:対応待ち` |
| 対応あり | `wib-action-ready` AND スター付き | `WIB:対応あり` |

`作業ビューを開く` を押すと、次の処理を行います。

1. `/api/thunderbird/imap-target` から WIB config の IMAP 対象情報を取得する。
2. Thunderbird 内の対応 IMAP アカウントを自動解決する。
3. `config.yaml` で指定された mailbox を解決する。
4. WIB 専用メールタブが存在すれば再利用する。
5. 専用タブが閉じられていれば新規作成する。
6. `mailTabs.setQuickFilter()` で選択した WIB タグ AND スター付き条件を適用する。
7. 専用タブを active にする。
8. `tabTitle.setTitle()` で `WIB:<ビュー名>` に表示タイトルを変更する。

ビューを切り替えても新しいタブは増えず、同じ WIB 専用タブの Quick Filter とタイトルだけが切り替わります。

この方式は実機で、WIB config からの対象アカウント自動解決、専用タブ再利用、6 ビュー切替、`WIB:○○` タブ名追随まで確認済みです。

### Quick Filter とスター

標準 Quick Filter API では WIB が必要とする Thunderbird の「返信済み」状態を直接条件に含めないため、WIB タグに加えてスターを現在注目対象の条件として使います。

たとえば `wib-answer` が履歴として残っていても、同期側でスターが外れれば `返信必要` 作業ビューには表示されません。

Quick Filter の条件定義は `background.js` の WIB プリセットに閉じ込め、FastAPI 側から Thunderbird API の具体的な引数を渡しません。

### `imapAccounts` Experiment

Thunderbird の公開 `accounts` API だけでは、WIB config と照合するために必要な incoming server の `hostname` / `username` / `port` を直接利用しないため、`experiments/imap_accounts/` の最小 Experiment API を使用します。

`imapAccounts` の責務は指定された Thunderbird account id の incoming server 情報を返すことだけです。

- アカウントを自動選択しません。
- Quick Filter を変更しません。
- IMAP password を読みません。
- SQLite や FastAPI にアクセスしません。

照合判断は `background.js` 側で行います。

### `tabTitle` Experiment

メールタブの任意タイトル変更は標準 API だけでは行わず、`experiments/tab_title/` の最小 Experiment API を使用します。

`tabTitle` の責務は、指定された Thunderbird タブのタイトルを変更することだけです。

- 作業ビューの種類を判断しません。
- IMAP タグを変更しません。
- SQLite や FastAPI にアクセスしません。

`imapAccounts` と `tabTitle` は Thunderbird 内部 API / UI 構造に依存するため、Thunderbird 更新時には互換性を確認してください。

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

## 13個の WIB タグを登録する

導入前スナップショットが存在する場合だけ、`13個のWIBタグを登録` が有効になります。

登録するタグ:

| key | 表示名 | 色 |
| --- | --- | --- |
| `wib-deadline` | `締切あり` | `#D32F2F` |
| `wib-schedule` | `スケジュール調整` | `#F57C00` |
| `wib-answer` | `返信必要` | `#1976D2` |
| `wib-review` | `見る・検討` | `#039BE5` |
| `wib-watch` | `注目` | `#7B1FA2` |
| `wib-bulk` | `一括処理` | `#424242` |
| `wib-pending` | `判定保留` | `#757575` |
| `wib-deadline-done` | `締切登録済み` | `#8E2424` |
| `wib-schedule-done` | `スケジュール対応済み` | `#A65300` |
| `wib-waiting-reply` | `返信待ち` | `#388E3C` |
| `wib-waiting-action` | `対応待ち` | `#7CB342` |
| `wib-action-ready` | `対応あり` | `#558B2F` |
| `wib-requested` | `依頼済み` | `#795548` |

同じ key がすでに存在する場合は重複作成せず、表示名と色を WIB 定義へ合わせます。

既存の WorkInBox 管理外タグは削除しません。

## 復元

復元方法は2つあります。

### 保存済みスナップショットから復元

`保存済みスナップショットから復元` を押します。

### JSON から復元

`JSONから復元` を押し、以前書き出したバックアップ JSON を選択します。

復元処理は次を行います。

1. 現在存在するWIBタグ定義（旧`wib-important` / `wib-batch`を含む）を削除する。
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
- 通常の INBOX タブの Quick Filter を WIB 作業ビュー用に上書きしない。
- WIB 作業ビュー用の対象 IMAP アカウントを Extension 側で二重管理しない。
