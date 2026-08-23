# WorkInBox Current Work

## 状態

作業中（実運用テスト継続）

## 現在の対象

- 親 Issue: #5 `docs/design.md 追従実装`
- #6〜#16 の実装 Issue: すべて Closed
- 残っている作業: #17〜#25 の実機確認
- 現在位置: 実機テストを開始できる状態。通常運用の中で #17〜#25 を順次確認する

## GitHub / git の現在状態

### GitHub

- 親 Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17〜#25: Open
- #16 `Thunderbird Bridge / Quick Filter を docs/design.md に合わせる`: Closed
- 今回の作業では Issue の Close / 作成 / 更新は行っていない。
- Actions はこの実行環境からGitHubへ接続できず、`3f2bc0b` の結果を未確認。

### ローカル git

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

### 0-7. #22 Thunderbird通常終了ボタン

- Thunderbirdで表示中の通常ワークフローメールを、Extensionボタン1回で終了する機能を追加した。
- 既存タグを保持して `一括処理` を追加し、スターを外す。
- 通常タグがないメールは変更せず、専用ワークフロー等の誤終了を防ぐ。
- Thunderbird 153実機では同時更新時にスターだけが外れたため、`一括処理` を先に追加・検証してからスターを外す2段階処理へ修正した。

### 0-6. 専用ワークフロー画面のIMAP確認高速化

- 実機DBのactiveメール27件に対し、締切画面は最大54回、スケジュール画面は最大27回IMAP接続を作り直す構造だった。
- 複数メールのlive IMAPタグを1接続でまとめて確認する処理を追加した。
- 締切AI抽出前確認と、締切・スケジュール画面表示のタグ確認に一括取得を使用するようにした。
- desktop実機で画面切替が速くなったことを確認した。

### 0-5. #17 実機報告と締切誤判定の終了操作

- #17 の実メールへのAI初期タグ付けは、利用者確認で概ね良好だった。
- #17 は完了条件を満たしたものとしてClose許可済みだが、GitHub APIへ接続できずClose操作は未反映。
- `締切あり` / `スケジュール調整` は再現率重視のため誤判定が一部あることを確認した。
- 締切候補が存在しても、メール全体を `締切なし` と一度で判断し、未確定候補をまとめて却下して終了できるようにした。
- 正式登録済みの締切が存在する場合は一括終了を拒否する。
- 実機で一括終了は成功したが、ダッシュボード `締切あり 1` に対して詳細0件となる不一致を確認した。
- ダッシュボードの `締切あり` / `スケジュール調整` を詳細画面と同じWIB activeメールに限定して修正した。
- 修正後、ダッシュボードの `締切あり` 件数と締切詳細の件数が一致することを実機確認した。
- #23 の締切登録支援について、候補の登録・修正・個別却下、登録完了タグ、全却下、候補0件、一括終了、他ワークフローとの共存、Thunderbird元メール導線をすべて実機確認した。
- #23 は完了条件を満たした。Close許可済みだが、GitHub APIへ接続できずClose操作は未反映。
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

残作業は実機確認 #17〜#25。

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

現時点で #6〜#16 はすべて Close しているが、#17〜#25 の実機確認が Open のため、
#5 は Open のまま維持されている。

実機確認の結果、設計・実装上の修正が必要になった場合は新しい実装 Issue を作成し、
修正・自動テスト・Actions を完了してから再度実機確認する。

## 中断理由

通常同期とThunderbird作業ビューが実機で動く状態になったため、しばらく通常運用でテストする。

新しい設計判断待ちによる中断ではない。

## 再開時に最初に行うこと

1. `docs/development_working_agreement.md` を読む。
2. この `docs/current_work.md` を読む。
3. `git status -sb` でローカル `main` と `origin/main` の差を確認する。
4. ローカル `main` と `origin/main` が一致し、未 push commit がないことを確認する。
5. GitHub #5 と #17〜#25 の状態を確認する。
6. commit `3f2bc0b` までのGitHub Actions結果を確認する。
7. 通常運用中に見つかった違和感・エラー・確認済み項目を利用者へ確認する。
8. `docs/manual_test_runbook.md` に従い、#24 + #25 の継続確認から再開する。
9. 新しい設計判断が不要なら、残りの実機確認へ進む。

## 設計判断待ち

なし。

実機確認の結果、新しい設計判断が必要になった時点で停止して利用者へ確認する。
