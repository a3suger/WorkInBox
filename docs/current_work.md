# WorkInBox Current Work

## 状態

中断中（メール閲覧画面のWIB操作メニューについて設計を協議中）

## 現在の対象

- 親 Issue: #5 `docs/design.md 追従実装`
- #6〜#16 の実装 Issue: すべて Closed
- 残っている実機確認: #18〜#22・#24・#25
- 追加実装Issue: #26・#27・#31・#32 Closed、#28〜#30・#33 Open
- 現在位置: Extension `0.3.10`の操作しないメニュープレビューを確認し、各項目へ割り当てる動作を協議中

## GitHub / git の現在状態

### GitHub

- 親 Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17・#23: Closed
- 実機確認 Issue #18〜#22・#24・#25: Open
- 追加実装 Issue #26・#27・#31・#32: Closed
- 追加実装 Issue #28〜#30・#33: Open
- #16 `Thunderbird Bridge / Quick Filter を docs/design.md に合わせる`: Closed
- 2026-08-26 に実運用で見つかった改善を #26〜#29 として作成した。
- #26 は実装・自動テスト・実機確認を完了しClosed。
- #27 は実装・自動テスト・実機確認を完了しClosed。表示先をタブ／新しいウィンドウから選べるようにする追加要望は #30 として作成した。
- 2026-08-30 に、WIB接続なしでも通常作業を継続するExtension内ダッシュボードを #31 として作成し、一度Closed。2026-08-31の追加要望を受けて再Openした。
- 2026-09-01 に、Extensionの締切サマリーとThunderbirdからの限定CalDAV双方向編集を #32 として作成した。詳細仕様は`docs/limited_caldav.md`。
- 2026-09-02 に #31 の追加調整と実機確認を完了してClosedした。通常の「受信ボックス」状態へ戻ったWIB作業タブの再利用不具合は #33 へ分離した。
- 2026-09-02 に #32 の限定CalDAV実装・自動テスト・Actions・実機確認を完了してClosedした。
- 最新確認済みActionsは run `33533359247` success、対象commitは `d6942c6`。

### ローカル git

2026-08-30 中断処理開始時、note側のローカル`main`と`origin/main`は`13e968a`で一致し、作業ツリーはclean。#31の最終commitは`13e968a Align extension dashboard counts with work views`。ローカル自動テストは142件成功、GitHub Actions run `33306375397`もsuccess。

2026-08-28 中断時、note側のローカル`main`と`origin/main`は`1666fd2`で一致し、作業ツリーは引き継ぎ文書更新前までclean。#27のローカル自動テストは136件成功、GitHub Actions tests #186もsuccess。#27は実機確認結果をコメントしてClosedし、追加要望 #30を作成した。この中断記録のみ未commit。

2026-08-27 の #26 実装は、このCodexタスクで `.git` が読み取り専用だったためGitHubのWeb編集画面から `main` へ直接反映した。GitHub上の実装commitは `910a9bf`〜`ffed629`。最終Actions run `33034122741`（tests #183）はsuccess。ローカル自動テストは `134 tests OK`。

note側 `/Users/akira/PycharmProjects/WorkInBox` のローカルHEADと`origin/main`参照は `70d3754` のままで、#26と同内容の変更10ファイルが未commit状態で残っている。この状態では直ちに `git pull` しない。再開時にGitHub `main` を正として、安全にローカルを同期する。desktop側がcleanなら通常の `git pull` でよい。

2026-08-27 再開時、note側は退避stashとGitHub最新版の内容が同一であることを確認し、stashを削除した。ローカル`main`と`origin/main`は`a0fc065`で一致し、作業ツリーはclean。desktop側も`70d3754..a0fc065`をpullしてWIBを再起動済み。

2026-08-26 作業再開時、ローカル `main` と `origin/main` は `e8daea8` で一致し、未 push commit、未 commit 変更はなかった。
GitHub Actions run `32859425927`（tests #172）は `e8daea8` に対してsuccess。

2026-08-25 中断時、ローカル `main` と `origin/main` は `94b0aec` で一致し、未 push commit、未 commit 変更はなかった。
VTODOの `mid:` 関連リンク実装は `deb566c`、実機確認記録は `94b0aec`。ローカル自動テストは `131 tests OK`。直近Actionsはこの実行環境から確認できていない。

2026-08-24 中断時、ローカル `main` と `origin/main` は `4901ff0` で一致し、未 push commit、未 commit 変更はなかった。
直近 commit `4901ff0 Add one-click normal workflow completion` には、Thunderbird Extension `0.2.10` の通常終了ボタンと旧 `wib-batch` 互換対応が含まれる。
ローカル自動テストは `129 tests OK`。`4901ff0` の GitHub Actions はこの実行環境から確認できていない。

2026-08-23 作業再開時、ローカル `main` と `origin/main` は `991cef0` で一致し、未 push commit、未 commit 変更はなかった。
GitHub API は実行環境の接続制限により確認できなかった。

2026-08-23 中断時の履歴:

```text
3f2bc0b Fix Thunderbird bridge IMAP target URL
3d86028 Fix Thunderbird 153 work view compatibility
4f503f1 Avoid mailbox searches during TriageBox relation checks
0aa38ff Prevent TriageBox reply lookup stalls
daf237a Use progress runtime for legacy web entry point
7af3360 Show synchronization phase and progress
```

中断処理開始時点でローカル `main` と `origin/main` は `3f2bc0b` で一致し、未 push commit、未 commit 変更はなかった。

### 2026-08-23 引き継ぎ時の再確認

- GitHub Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17〜#25: Open
- 最新 Actions: run `32571406463` success
- ローカル自動テスト: `119 passed, 6 subtests passed`

### 2026-08-23 実機確認の到達点

- Thunderbird の既存「プライベート」タグを WIB の `一括処理` へ変換する後段フィルターを追加し、実行済み。
- 通常同期の処理段階と件数をWeb UIで確認できるようになった。
- TriageBox が `2 / 1349件` 付近で停滞する問題を修正し、実機で通常同期がスムーズに完了することを確認した。
- AI判定には時間がかかったが、利用者判断では想定範囲内だった。
- Thunderbird 153.0.2esr で作業ビューを開けない問題を2段階で修正した。
- 最終的に WIB の「Thunderbirdで確認」から対象一覧が表示されることを実機確認した。
- しばらく通常運用でテストするため、#17〜#25 は Open のまま継続する。
- ローカル自動テスト: `125 tests OK`（既知の subtest を含む）

## 最新の「作業再開」以降に完了した作業

### 0-10. #31 Extension内ダッシュボード

- Thunderbird内にExtension専用ダッシュボードを追加し、WIBの接続状態とThunderbird由来の作業件数を表示した。
- WIB停止中・SSH tunnel切断中も、保存済みIMAP対象設定を使って件数更新とThunderbird作業ビューを利用できるようにした。
- WIBへ`/api/health`と`/api/extension/bootstrap`を追加し、credentialやメール本文をExtensionへ保存しない境界を確定した。
- Thunderbird検索APIへ日付・スター・タグ条件を先に渡し、INBOX全件をExtensionへ読み込まないよう集計を高速化した。
- 未着眼2件数と、その2カードから開くThunderbird作業ビューだけに`new_mail_lookback_days`を適用した。
- 締切あり・スケジュール調整を含む全作業件数をThunderbird一覧と同じ`対象タグ + ★`へ統一した。
- Extensionの最終バージョンは`0.3.3`。実機でオンライン、WIB停止、復旧、件数更新、作業ビュー、期間制限、件数一致を確認した。
- commitは`09eb805`、`f27510c`、`943b4f7`、`13e968a`。各GitHub Actionsはsuccess、最終runは`33306375397`。
- #31へ実機確認結果をコメントし、Closedした。
- その後のdesktop実機確認と操作改善要望を受け、2026-08-31に#31を再Openした。`0.3.4`では未着眼を合計と未読 / 既読内訳の1カードへ統合し、WIB WebとExtensionのどちらからも期間付きの1作業ビューを開く。接続状態欄にはオンライン時だけ使える通常同期ボタンを追加した。ローカル自動テストは143件成功。

### 0-9. #26 VTODOからWIB締切詳細を開いて編集する

- VTODOの `mid:` 元メールリンクを維持し、説明欄へ「締切の確認・修正」URL `/deadlines/{deadline_id}` を追加した。
- WIBに登録済み締切の詳細画面を追加し、タイトル・期限・メモを編集できるようにした。
- 修正内容は正本のSQLiteへ保存し、次回の `deadlines.ics` 取得時にVTODOへ反映する。
- 従来の `/deadlines/{deadline_id}/source-message` は既存VTODOとの互換用に維持した。
- `docs/design.md` と `docs/deadline_workflow.md` を現行実装へ追従した。
- ローカル自動テストは `134 tests OK`。
- GitHub Web編集の都合で、実装は `910a9bf`〜`ffed629` の10commitに分かれている。
- 最終GitHub Actions run `33034122741`（tests #183）はsuccess。
- Thunderbird実機で、ToDoの「締切の確認・修正」リンクがnoteの外部ブラウザでWIB画面を開くことを確認した。
- WIBでの保存とToDoへの再反映を確認した。
- 同じToDoの`mid:`関連リンクから元メールが引き続き素早く開くことを確認した。
- #26 の完了条件を満たしたためClosed。

### 0-8. VTODOから締切の元メールを開く導線

- 実運用で最も困っている締切確認を優先し、VTODOへThunderbird標準の `mid:` 元メールURLを追加した。
- Thunderbirdのカレンダー／ToDo画面で主URLを開くと、Message-IDから追加クリックなしで元メールを直接表示する。
- 説明欄には締切IDベースのWIB案内URLも追加し、外部ブラウザまたはBridge未接続時は締切・件名・差出人・受信日時をWIBページに表示する。
- Extensionバージョンを `0.2.11` に更新した。
- ローカル自動テストは `131 tests OK`。
- Thunderbird 153実機ではVTODOの `mid:` URLが「関連リンク」として表示される。その関連リンクをクリックし、外部ブラウザを経由せず元メールが素早く表示されることを確認した。「主URL」という別の操作対象はない。
- 説明欄のWIB案内URLを外部ブラウザで開いた場合の情報表示と、元メールが見つからない場合の失敗表示は未確認。

### 0-7. #22 Thunderbird通常終了ボタン

- Thunderbirdで表示中の通常ワークフローメールを、Extensionボタン1回で終了する機能を追加した。
- 既存タグを保持して `一括処理` を追加し、スターを外す。
- 通常タグがないメールは変更せず、専用ワークフロー等の誤終了を防ぐ。
- Thunderbird 153実機では正式な `wib-bulk` タグ定義が未登録で、旧 `wib-batch` 定義だけが残る環境を確認した。Thunderbird は同じ表示名の正式タグ作成を拒否するため、終了ボタンは登録済みの正式キーを優先し、なければ旧キーまたは同名タグを互換利用してからスターを外す。
- 直後のMessageHeader再取得が古いタグ状態を返してスター解除を止めたため、タグ定義の事前確認と更新完了待ちに変更した。
- Thunderbird 153.0.2esr 実機で、元の通常タグを保持したまま「一括処理」が付き、スターが外れることを確認した。
- Extension バージョンは `0.2.10`、ローカル自動テストは `129 tests OK`。

### 0-6. 専用ワークフロー画面のIMAP確認高速化

- 実機DBのactiveメール27件に対し、締切画面は最大54回、スケジュール画面は最大27回IMAP接続を作り直す構造だった。
- 複数メールのlive IMAPタグを1接続でまとめて確認する処理を追加した。
- 締切AI抽出前確認と、締切・スケジュール画面表示のタグ確認に一括取得を使用するようにした。
- desktop実機で画面切替が速くなったことを確認した。

### 0-5. #17 実機報告と締切誤判定の終了操作

- #17 の実メールへのAI初期タグ付けは、利用者確認で概ね良好だった。
- #17 は完了条件を満たし、GitHubでClosedになっていることを確認した。
- `締切あり` / `スケジュール調整` は再現率重視のため誤判定が一部あることを確認した。
- 締切候補が存在しても、メール全体を `締切なし` と一度で判断し、未確定候補をまとめて却下して終了できるようにした。
- 正式登録済みの締切が存在する場合は一括終了を拒否する。
- 実機で一括終了は成功したが、ダッシュボード `締切あり 1` に対して詳細0件となる不一致を確認した。
- ダッシュボードの `締切あり` / `スケジュール調整` を詳細画面と同じWIB activeメールに限定して修正した。
- 修正後、ダッシュボードの `締切あり` 件数と締切詳細の件数が一致することを実機確認した。
- #23 の締切登録支援について、候補の登録・修正・個別却下、登録完了タグ、全却下、候補0件、一括終了、他ワークフローとの共存、Thunderbird元メール導線をすべて実機確認した。
- #23 は完了条件を満たし、GitHubでClosedになっていることを確認した。
- ダッシュボード件数一致は #24 の部分確認として扱い、残りの完了条件を確認するまで #24 はOpenを維持する。

### 0-4. ダッシュボード未着眼件数の期間限定

- `未着眼・未読` / `未着眼・既読` の件数を `imap.new_mail_lookback_days` の直近期間に限定した。
- Thunderbirdの未着眼ビューは受信箱全体のままとし、件数が一致しない場合があることをダッシュボードに明記した。

### 0-3. Thunderbird 153 作業ビュー互換修正

- Thunderbird 153.0.2esr の同梱実装と Extension の custom Mail View 呼び出しを照合した。
- `WIB 未着眼` の適用時に built-in all mail の番号 `0` を渡していた箇所を、custom view名を渡す形へ修正した。
- 通常ビューへ戻す際に存在しない番号 `-1` を渡していた箇所を、all mail の番号 `0` へ修正した。
- Thunderbird content script の相対URLがExtension側へ解決されないよう、IMAP対象APIのURLを表示中のWIBページから明示的に構築するよう修正した。

### 0-2. TriageBox の長時間停止対策

- 実機同期で `TriageBox: 未読メール確認 — 2 / 1349件` のまま進まない事象を調査した。
- 未登録の返信スレッドについて、返信履歴中の全 Message-ID を受信箱全体から順番に検索していたことが原因だった。
- WIB のローカル relation を先に確認し、未登録スレッドでは受信箱全体の Message-ID 検索を行わないようにした。
- 専用ワークフローのタグ付与時と、同じ未読取得内で対象タグを確認した時に relation を登録するようにした。
- 同じ Message-ID の検索結果を同期処理中に再利用するようにした。
- IMAP 接続に既定30秒のタイムアウトを追加した。
- 個々のメールで時間がかかった場合に `TriageBox: 返信関係確認 — 現在件 / 全件` と表示するようにした。
- ローカル自動テスト: `125 passed, 6 subtests passed`

### 0-1. 実機テスト準備と同期進捗表示

- 実機テスト再開用の単一手順書 `docs/manual_test_runbook.md` を追加した。
- 通常同期中にTriageBox / TrackingBoxのどの段階かをWeb UIへ表示するようにした。
- 未読取得・未読確認・既存active確認・新着取り込み・AI対象確認・AI初期分類について、処理済み件数 / 対象件数 / エラー件数を2秒間隔で表示する。
- ローカル自動テスト: `119 passed, 6 subtests passed`

### 1. 未着眼条件の正式設計修正

`docs/design.md` の未着眼条件を次で確定した。

```text
未着眼・未読
= スターなし
AND 未読
AND 一括処理なし

未着眼・既読
= スターなし
AND 既読
AND 一括処理なし
```

### 2. #15 ダッシュボード追従修正

ダッシュボードの未着眼集計を上記条件へ追従させた。

旧 `wib-batch` は互換のため `一括処理` 相当として除外している。

関連 commit:

- `c4fd3e1` Correct unattended mail conditions
- `16db4df` Align dashboard unattended mail conditions
- `f035aab` Test bulk-only unattended exclusions

### 3. #16 Thunderbird Bridge / Quick Filter 実装

実装内容:

- Thunderbird Extension に `WIB 未着眼` custom Mail View 用 Experiment API を追加
- 固定条件を `スターなし AND 一括処理なし` として実装
- 旧 `wib-batch` 互換も除外
- `未着眼・未読` は未読 Quick Filter を重ねる
- `未着眼・既読` は同じ custom Mail View を未読フィルターなしで開く
- `返信必要` / `見る・検討` / `注目` は `対象タグ + ★` の Quick Filter として維持
- WIB ダッシュボード `data-wib-open-work-view` と Thunderbird Bridge を接続
- popup の旧 PoC 表記を更新
- `docs/thunderbird_bridge.md` を現行設計へ追従
- `tests/test_thunderbird_work_views.py` を追加

主な commit:

- `5a92843` Implement unattended Thunderbird mail view
- `12a6b95` Register unattended mail view experiment
- `5394043` Reset custom mail view for normal work views
- `5a11340` Connect unattended and active Thunderbird work views
- `f9cb6da` Connect WIB dashboard to Thunderbird work views
- `fb6df78` Align Thunderbird work view controls
- `076e977` Test Thunderbird work view contract
- `3c28ec5` Align Thunderbird Bridge with current design

GitHub Actions:

- #149 success

#16 は実装・自動テスト・Actions 完了として Closed。
Thunderbird 実機確認は #25 に分離済み。

## 現在の残作業

実装 Issue #6〜#16 はすべて完了している。

実機確認 #17・#23 と追加実装 #26・#27・#31 は完了しClosed。実機確認 #18〜#22・#24・#25と、追加実装 #28〜#30・#32・#33が残っている。

### 追加実装Issue

1. #28 `スケジュール調整支援に「スケジュール調整は不要」を追加する`
2. #29 `Activeメール一覧をタグで絞り込めるようにする`
3. #30 `元メールをタブまたは新しいウィンドウで開く設定を追加する`
4. #31 `WIB接続なしでも通常作業を継続できるExtension内ダッシュボードを追加する`
5. #32 `Extension締切サマリーと限定CalDAV双方向編集を追加する`
6. #33 `WIB作業タブが通常の受信ボックス状態になった場合の再利用を修正する`

#31 は追加調整、Actions、実機確認を完了してClosedした。#28〜#30・#32・#33はOpenのまま維持する。

### 実機確認の進め方

通常の受信箱と実際の業務メールを使い、次のまとまりで確認すると重複作業を減らせる。

1. #24 + #25: WIB ダッシュボードの件数・導線と Thunderbird 作業ビューを同じ受信箱で確認する
2. #17 + #22 + #23: AI 初期分類から通常終了 / Record 保存 / 締切登録までを、該当する実メールごとに確認する
3. #18 + #19 + #20 + #21: 実際のスケジュール調整支援 1 件を M1 として、支援依頼 M2、支援者返信 M3、元スレッド継続 M4 の順にまとめて確認する

人工的なテストメールは作らず、各 Issue の「実施タイミング」に従う。条件に合う実メールがまだない項目は Open のまま維持する。

### Issue 順の確認候補

1. #17 AI 初期分類を実メールで確認する
2. #18 対応待ち → 対応あり を実メールで確認する
3. #19 M1/M2/M3 relation を実メールで確認する
4. #20 M2 送信後の M1「依頼済み」を実メールで確認する
5. #21 専用ワークフローの current focus を実メールで確認する
6. #22 通常ワークフロー終了と Record 保存を実機確認する
7. #23 締切登録支援を実メールで確認する
8. #24 WIB ダッシュボードを実運用で確認する
9. #25 Thunderbird の WIB 作業ビューを実機確認する

ただし、実機確認はまとめて行った方が負担が小さい場合がある。
再開時に各 Issue の確認手順を読み、同一メールや同一環境でまとめられるものを整理してから開始してよい。

## 親 Issue #5 の完了条件

#5 の完了条件は次のとおり。

- 追従 Issue がすべて Close
- `docs/design.md` と詳細設計・実装の既知差分が解消

現時点で #6〜#17・#23・#26・#27・#31 はCloseしているが、#18〜#22・#24・#25・#28〜#30・#32・#33がOpenのため、
#5 は Open のまま維持されている。

実機確認の結果、設計・実装上の修正が必要になった場合は新しい実装 Issue を作成し、
修正・自動テスト・Actions を完了してから再度実機確認する。

## 現在の作業状況

#31 はExtension内ダッシュボードの目的、Thunderbird由来の集計、WIBヘルスチェック、オンライン・オフラインの責務境界、キャッシュ、性能、API、完了条件を `docs/extension_dashboard_proposal.md` に整理した。既存WIB Web UIは維持し、全面移植やオフライン更新キューは対象外とした。追加調整と実機確認まで完了し、2026-09-02にClosedした。

初回実装ではWIBへ`/api/health`と`/api/extension/bootstrap`を追加し、Extension `0.3.0`へ専用ダッシュボードタブを追加した。Thunderbirdの対象mailboxをメッセージヘッダーだけで集計し、未着眼2件数には`new_mail_lookback_days`、その他には`対象タグ + ★`を適用する。接続設定と直近集計をExtension内へ保存し、WIB停止中も作業ビューを開ける。30秒間隔ではhealthだけを確認し、件数再集計は初回、手動更新、メール状態変更時に限定した。

実機確認を受け、Extension `0.3.1`ではThunderbird検索APIへ日付・スター・タグ条件を先に渡し、INBOX全件をExtensionへ読み込まないよう集計を高速化した。さらに`0.3.2`では、ダッシュボードの未着眼2カードから開くcustom Mail Viewにも`new_mail_lookback_days`を渡し、件数と一覧の対象期間を一致させた。

Extension `0.3.3`では、締切あり・スケジュール調整の件数だけが完了タグ付きメールを除外してThunderbird作業ビューと不一致になっていた問題を修正した。Extensionダッシュボードの全作業件数を、表示一覧と同じ`対象タグ + ★`に統一した。

Extension `0.3.4`では、未着眼を合計と未読 / 既読内訳の1カード・1作業ビューに統合した。WIB Web側もbootstrapから`new_mail_lookback_days`を取得してExtensionへ渡すため、desktopのWIB Web導線にも期間制限がかかる。Extensionの接続状態欄へ通常同期ボタンと`POST /api/sync`を追加し、オンライン時だけ開始可能、実行中は2秒間隔で状態確認する。ローカル自動テスト143件成功。commit、Actions、実機確認は未実施。

実運用で、支援者への依頼メールに元メールの内容が含まれず依頼時に文脈を伝えられないことを確認した。Extension `0.3.5`では、M2をM1へのReplyにはせず別スレッドのまま維持し、Thunderbirdの本文内転送としてM1を含める。`X-WorkInBox-Origin-Message-ID`、宛先・Cc、依頼内容に応じた件名と本文冒頭、送信後の`依頼済み`処理は維持する。ローカル自動テスト143件成功。commit、Actions、実機確認は未実施。

Extension `0.3.6`では、`スケジュール調整 + 依頼済み`の起点メールを、WIB Webのダッシュボード件数とスケジュール調整一覧、およびExtensionダッシュボード件数から除外する。依頼後の作業は依頼メール側の`対応待ち` / `対応あり`で確認する。

Extension `0.3.7`では、`締切あり`から`締切登録済み`を、`スケジュール調整`から`依頼済み`と`スケジュール対応済み`を除外する専用custom Mail Viewを追加する。Web・Extensionの件数、WIB Web一覧、Thunderbird作業ビューで未処理対象を揃える。

実機で、self-Ccの支援依頼M2に関連ヘッダーがありM1へ`依頼済み`も付いた一方、通常同期後もM2へ`対応待ち + ★`が付かないことを確認した。TriageBoxが未読メールだけを検索し、同期前に既読になったM2をチェックポイントの外へ送っていたことが原因。直近期間の`X-WorkInBox-Origin-Message-ID`付きメールを未読チェックポイントとは別に毎回検索し、既読M2も回収するよう修正した。

既読回収後も実機でM2へタグとスターが付かなかった。M2の関連ヘッダーは存在するため、追加で、送信Identity/別名が`config.identity`の自己アドレスと一致しない場合もWIB関連ヘッダーを優先して支援依頼として処理するよう修正した。

desktopのINFOログで、M2候補2件はいずれもTriageBoxへ到達した後、M1をMessage-IDで受信箱全体から検索する処理が各60秒でread timeoutになっていたことを確認した。M1はWIB SQLiteにUIDが保存済みのため、保存済みUIDでフラグを直接確認し、UIDがない場合だけ従来のMessage-ID検索へフォールバックするよう修正した。

M2への`対応待ち + ★`が成功した後、M2への返信M3に`対応あり + ★`が付かないことを確認した。対応待ちrelationを持つM2のMessage-IDを基準に、直近期間の`In-Reply-To` / `References`からM3を既読でも回収する。また、M3処理時のM2確認も保存済みUIDを使い、受信箱全体のMessage-ID検索によるタイムアウトを避けるよう修正した。

#32は第1段階の締切サマリーに加え、SQLiteへ着手日時・完了状態・重要度・更新世代を追加し、loopback限定の`/caldav/deadlines/`を実装した。既存ToDoの取得と編集、完了済みのサマリー除外、ETag競合拒否、Web編集時のCalDAV専用項目保持に対応した。旧`deadlines.ics`は移行確認用に残している。commit `d6942c6`、自動テスト155件、Actions run `33533359247`、実機確認のすべてが成功し、#32をClosedした。

Extension `0.3.9`では、`一括処理`または旧互換タグが付きスターのないメールをmailbox全体から数え、ダッシュボードの「整理済みメール / アーカイブ待ち」に表示する。同じ条件のThunderbird作業ビューを開き、定期的な確認とアーカイブへ進める。ダッシュボード全体の情報設計・配置見直しは、実運用するカードが揃った段階の別作業として扱う。

Extension `0.3.10`では、メール閲覧画面の「WIB:通常ワークフロー終了」を、通常フローと専用フローの構成を確認する「WIB操作メニュー」へ置き換えた。現段階はUIプレビューであり、項目を選んでもタグ、スター、WIB画面を変更しない。実機でメニュー構成を確認した後、表示条件と各操作の動作を決定して実装する。

Extension `0.3.11`では、スペースツールバーへの追加を見据え、正式アイコンを青い線画の受信トレイと中央の丸みのある`w`を組み合わせたデザインへ更新した。複数の比較案を確認し、利用者がB案を基にした丸なしの小さい`w`中央配置版を採用した。

Extension `0.3.12`では、正式アイコンを使ったWorkInBoxボタンをThunderbirdのスペースツールバーへ常設した。ボタンはExtension内ダッシュボードを専用スペースとして開いて同じタブを再利用し、popupのダッシュボード導線も同じスペースへ合流する。実機で、Extension再読み込み後に左側のスペースツールバーへアイコンが表示されること、クリックでダッシュボードが開くこと、別スペースへ移動後の再クリックで新しいタブを増やさず同じダッシュボードへ戻ることを確認済み。

Extension `0.3.13`では、日常の入口をスペースツールバーへ一本化するため、メニューバーのWorkInBoxボタンを削除した。従来のpopupにある接続・作業ビュー・タグ管理等は`設定・ツール`画面として維持し、Extension内ダッシュボード右上の歯車ボタンから開く。アドオンマネージャーの設定からも引き続き利用できる。実機では、メニューバーからボタンが消えること、歯車から設定・ツール画面がThunderbird内で開くこと、各操作が従来どおり使えることを確認する。

Extension `0.3.14`では、`設定・ツール`画面から日常操作と重複するExtensionダッシュボード、WIB Web UI、WIB作業ビューを削除した。設定・ツールはArchive索引設定とWIBタグの登録・バックアップ・復元だけを扱う。実機では3区画が表示されないことと、残した保守操作が従来どおり利用できることを確認する。

Extension `0.3.15`では、WIB操作メニューの専用フロー開始・再開を実装した。表示中メールのMessage-IDを取得し、締切またはスケジュール調整のタグとスターを付けた後、1枚だけ再利用する専用タブを開く。Extension内の起動画面がWIB healthを確認し、接続時はメール単位の`/deadlines/message`または`/schedules/message`へ遷移し、接続不可時は案内と再試行を表示する。Web側は対象メールだけを抽出・表示し、締切候補操作とスケジュール完了後もメール単位表示を維持する。通常フローと「締切なし」「スケジュール調整なし」は引き続き設計判断待ちのプレビューとする。

Extension `0.3.16`では、Thunderbirdの山括弧なしMessage-IDとSQLiteの山括弧付きMessage-IDをメール単位画面が完全一致で比較し、一覧にはあるメールを対象外と表示する問題を修正した。締切抽出と締切・スケジュール画面の絞り込みで、山括弧を除いたMessage-IDを照合する。

メニュー構成自体は利用者が理解できることを確認した。通常フローでは、現在付いているタグに対応する項目（例: `回答必要`が付いているときの「回答必要にする」）を選択不可にする案を検討中。複数の通常タグを許すか、分類変更時に以前の通常タグを外すか、通常タグを履歴として残すかは未決定であり、もう少し議論してから実装する。専用フローについても、開始・再開時のタグとスター、対象Message-IDを指定してWIB画面を開く動作、`締切なし`・`スケジュール調整なし`後に他フローが残る場合の終了規則を確定してから実装する。プレビュー中は従来の通常終了操作も実行されないため、実運用ではWIB Web側の通常終了を使用する。

Extension `0.3.9`までの#31完了条件は実機確認済み。WIB作業タブが通常の「受信ボックス」状態へ戻った場合にダッシュボードからの切り替えが失敗することがあるため、既存タブが本当にWIB専用状態か検証して安全に再利用する修正を#33へ分離した。当面は該当タブを閉じてから作業ビューを開き直す。

#26 は実装・自動テスト・Actions・実機確認を完了した。ToDoのWIBリンクはnoteの外部ブラウザで開く現行動作を完了条件として扱う。Thunderbird内部表示は可能性があるが、VTODO内の通常HTTPリンクをExtensionで確実に横取りする追加設計が必要なため、#26には含めない。

#27 はcommit `1666fd2`でWIB内の元メール導線を`mid:`優先へ変更し、従来のExtension検索を「見つからない場合は検索」として維持した。自動テスト136件とActions tests #186が成功。Active、締切、スケジュール調整、判定保留、締切詳細、Records等の実機確認で、元メールが外部ブラウザを経由せず素早く正しく開き、予備検索も機能することを確認してClosedした。現在は新しいウィンドウで開くため、タブとの選択設定を追加する要望を #30へ分離した。

#22 は通常終了の主要遷移を確認済み。次回は、通常タグがないメールで終了ボタンが何も変更しないことと、Record保存終了の3項目を確認する。#24・#25および#18〜#21の実運用確認も残っている。

実運用中の改善要望として、スケジュール調整支援にもAIの誤判定があるため、現在の「自分で対応済み」とは別に「スケジュール調整は不要」と一度で判断できるボタンを追加する案を検討する。再開時に、タグ解除・通常ワークフローへの接続・履歴の扱いを締切支援の「このメールには締切なしとして終了」と照合してから設計・実装する。

アクティブメール一覧では各メールに対して複数の操作ができるため、タグごとに表示を絞り込めるフィルタを追加する案も検討する。再開時に、通常ワークフロー・専用ワークフロー・待機状態のどのタグを対象にするか、複数タグ指定をAND/ORのどちらで扱うか、絞り込み状態を保持するかを整理してから実装する。

WIB操作メニューの動作は設計判断待ちである。

## 次に行うこと

1. WIB操作メニューの通常フローで、複数タグを許すか、分類変更時に旧タグを外すか、履歴をどう残すかを議論する。
2. 現在付いているタグの項目を選択不可にする表示と、専用フローの開始・再開・終了規則を確定する。
3. 合意後に各メニュー項目の動作を実装する。それまではExtension `0.3.10`を操作しないプレビューとして維持する。

## 設計判断待ち

- 通常フロータグを排他的な現在分類として扱うか、複数を履歴として共存させるか。
- 専用フロー終了時、ほかの未完了フローがない場合だけ`一括処理 + スター解除`へ進めるか。

実機確認の結果、新しい設計判断が必要になった時点で停止して利用者へ確認する。
