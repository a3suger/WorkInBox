# WorkInBox Current Work

## 状態

作業中（#31 Extension内ダッシュボード仕様案を作成）

## 現在の対象

- 親 Issue: #5 `docs/design.md 追従実装`
- #6〜#16 の実装 Issue: すべて Closed
- 残っている実機確認: #18〜#22・#24・#25
- 追加実装Issue: #26・#27 Closed、#28〜#31 Open
- 現在位置: #31 を作成し、`docs/extension_dashboard_proposal.md` に初回実装の仕様案を記録。実装はまだ開始していない

## GitHub / git の現在状態

### GitHub

- 親 Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17・#23: Closed
- 実機確認 Issue #18〜#22・#24・#25: Open
- 追加実装 Issue #26・#27: Closed
- 追加実装 Issue #28〜#31: Open
- #16 `Thunderbird Bridge / Quick Filter を docs/design.md に合わせる`: Closed
- 2026-08-26 に実運用で見つかった改善を #26〜#29 として作成した。
- #26 は実装・自動テスト・実機確認を完了しClosed。
- #27 は実装・自動テスト・実機確認を完了しClosed。表示先をタブ／新しいウィンドウから選べるようにする追加要望は #30 として作成した。
- 2026-08-30 に、WIB接続なしでも通常作業を継続するExtension内ダッシュボードを #31 として作成した。仕様案は `docs/extension_dashboard_proposal.md`。
- 最新確認済みActionsは run `33089524024`（tests #186）success、対象commitは `1666fd2`。

### ローカル git

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

実機確認 #17・#23 と追加実装 #26・#27 は完了しClosed。実機確認 #18〜#22・#24・#25と、追加実装 #28〜#31が残っている。

### 追加実装Issue

1. #28 `スケジュール調整支援に「スケジュール調整は不要」を追加する`
2. #29 `Activeメール一覧をタグで絞り込めるようにする`
3. #30 `元メールをタブまたは新しいウィンドウで開く設定を追加する`
4. #31 `WIB接続なしでも通常作業を継続できるExtension内ダッシュボードを追加する`

#31 は仕様案作成まで完了し、実装は未着手。利用者と初回実装範囲を確認してから設計へ統合し、実装する。#28〜#30もOpenのまま維持する。

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

現時点で #6〜#17・#23・#26・#27 はCloseしているが、#18〜#22・#24・#25・#28〜#31がOpenのため、
#5 は Open のまま維持されている。

実機確認の結果、設計・実装上の修正が必要になった場合は新しい実装 Issue を作成し、
修正・自動テスト・Actions を完了してから再度実機確認する。

## 現在の作業状況

#31 はGitHub Issueを作成し、Extension内ダッシュボードの目的、Thunderbird由来の集計、WIBヘルスチェック、オンライン・オフラインの責務境界、キャッシュ、性能、API候補、完了条件を `docs/extension_dashboard_proposal.md` に整理した。既存WIB Web UIは維持し、初回実装では全面移植やオフライン更新キューを対象外とする。実装はまだ開始していない。

#26 は実装・自動テスト・Actions・実機確認を完了した。ToDoのWIBリンクはnoteの外部ブラウザで開く現行動作を完了条件として扱う。Thunderbird内部表示は可能性があるが、VTODO内の通常HTTPリンクをExtensionで確実に横取りする追加設計が必要なため、#26には含めない。

#27 はcommit `1666fd2`でWIB内の元メール導線を`mid:`優先へ変更し、従来のExtension検索を「見つからない場合は検索」として維持した。自動テスト136件とActions tests #186が成功。Active、締切、スケジュール調整、判定保留、締切詳細、Records等の実機確認で、元メールが外部ブラウザを経由せず素早く正しく開き、予備検索も機能することを確認してClosedした。現在は新しいウィンドウで開くため、タブとの選択設定を追加する要望を #30へ分離した。

#22 は通常終了の主要遷移を確認済み。次回は、通常タグがないメールで終了ボタンが何も変更しないことと、Record保存終了の3項目を確認する。#24・#25および#18〜#21の実運用確認も残っている。

実運用中の改善要望として、スケジュール調整支援にもAIの誤判定があるため、現在の「自分で対応済み」とは別に「スケジュール調整は不要」と一度で判断できるボタンを追加する案を検討する。再開時に、タグ解除・通常ワークフローへの接続・履歴の扱いを締切支援の「このメールには締切なしとして終了」と照合してから設計・実装する。

アクティブメール一覧では各メールに対して複数の操作ができるため、タグごとに表示を絞り込めるフィルタを追加する案も検討する。再開時に、通常ワークフロー・専用ワークフロー・待機状態のどのタグを対象にするか、複数タグ指定をAND/ORのどちらで扱うか、絞り込み状態を保持するかを整理してから実装する。

新しい設計判断待ちによる中断ではない。

## 次に行うこと

1. #31 の仕様案と初回実装範囲を利用者と確認する。
2. 確定した責務境界を `docs/design.md` と `docs/thunderbird_bridge.md` へ統合する。
3. #31 を小さな実装単位へ分け、Extension内ダッシュボードの実装へ進む。
4. #28〜#30もOpenのまま維持し、#31との優先順を必要に応じて確認する。

## 設計判断待ち

なし。

実機確認の結果、新しい設計判断が必要になった時点で停止して利用者へ確認する。
