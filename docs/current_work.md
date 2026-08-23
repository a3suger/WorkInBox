# WorkInBox Current Work

## 状態

作業中断

## 現在の対象

- 親 Issue: #5 `docs/design.md 追従実装`
- #6〜#16 の実装 Issue: すべて Closed
- 残っている作業: #17〜#25 の実機確認

## GitHub / git の現在状態

### GitHub

- 親 Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17〜#25: Open
- #16 `Thunderbird Bridge / Quick Filter を docs/design.md に合わせる`: Closed
- #16 の最新実装 commit: `3c28ec56a8c457c1d26fe86e37d1656be5553dd3`
- 最新 GitHub Actions: run `32571406463` success (`88e7c50`)

### ローカル git

引き継ぎ確認開始時の履歴:

```text
88e7c50 docs: add work interruption and handoff process
aaee149 .gitignore の修正
3c28ec5 Align Thunderbird Bridge with current design
```

引き継ぎ確認開始時点でローカル `main` と `origin/main` は一致し、未 push commit、未 commit 変更はなかった。
以前未 push と記録されていた `aaee149` は push 済み。

### 2026-08-23 引き継ぎ時の再確認

- GitHub Issue #5: Open
- 実装 Issue #6〜#16: Closed
- 実機確認 Issue #17〜#25: Open
- 最新 Actions: run `32571406463` success
- ローカル自動テスト: `118 passed, 6 subtests passed`

## 最新の「作業再開」以降に完了した作業

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

チャット引き継ぎ基盤の整備と、ChatGPT 側 GitHub 接続不調のため。

新しい設計判断待ちによる中断ではない。

## 再開時に最初に行うこと

1. `docs/development_working_agreement.md` を読む。
2. この `docs/current_work.md` を読む。
3. `git status -sb` でローカル `main` と `origin/main` の差を確認する。
4. ローカル `main` と `origin/main` が一致し、未 push commit がないことを確認する。
5. GitHub #5 と #17〜#25 の状態を確認する。
6. 最新 GitHub Actions が run `32571406463` success 以後に変化していないか確認する。
7. 実機確認 #17〜#25 の内容を読み、まとめて実施できる確認を整理する。
8. 新しい設計判断が不要なら、残作業の先頭から再開する。

## 設計判断待ち

なし。

実機確認の結果、新しい設計判断が必要になった時点で停止して利用者へ確認する。
