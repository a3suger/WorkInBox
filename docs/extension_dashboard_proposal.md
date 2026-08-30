# Thunderbird Extension 内ダッシュボード仕様案

この文書は、WIB サーバーへ接続できない場合でも Thunderbird 上で通常のメール整理を継続できるようにするための検討メモである。

現時点では確定済みの正式設計ではない。実装開始前に必要な判断を整理し、確定内容を `docs/design.md` と `docs/thunderbird_bridge.md` へ統合する。

関連Issue: [#31 WIB接続なしでも通常作業を継続できるExtension内ダッシュボードを追加する](https://github.com/a3suger/WorkInBox/issues/31)

## 1. 目的

- WIB サーバーや SSH 接続が停止していても、Thunderbird だけで通常ワークフローを継続できるようにする。
- Extension 内に、接続状態と Thunderbird の現在状態を表示するダッシュボードを設ける。
- WIB を AI 判定、SQLite、relation、Record、専用ワークフローを担当するバックエンドとして位置付ける。
- 現在の WIB Web UI は維持し、初回実装で全面的なフロントエンド移行は行わない。

## 2. 初回実装の範囲

Thunderbird 内に `WorkInBox ダッシュボード` タブを追加する。

Extension のボタンからダッシュボードを開き、既に同じタブが存在する場合は再利用する。現在の popup に残す設定・保守機能と、ダッシュボードへ移す作業導線は実装時に整理する。

画面は次の2種類の情報を区別して表示する。

1. Thunderbird の現在状態から計算した情報
2. WIB API から取得した情報

## 3. 接続状態

画面上部に WIB との接続状態を表示する。

| 状態 | 表示 | 意味 |
| --- | --- | --- |
| 確認中 | 灰色 | ヘルスチェック実行中 |
| 接続中 | 緑 | WIB API と必要なバックエンドが利用可能 |
| 一部利用不可 | 黄色 | WIB は応答するが DB 等の一部に問題がある |
| 接続不可 | 赤 | WIB 停止、SSH tunnel 切断、timeout 等により接続できない |

併せて次を表示する。

- 最終接続成功日時
- WIB バージョン
- API 仕様バージョン
- 最終 WIB 同期日時
- 同期実行中かどうか
- `接続を再確認` ボタン

接続確認は Extension ダッシュボードを開いたとき、画面を再び前面にしたとき、一定間隔、および手動操作時に行う。初期値として timeout は3秒、定期確認は30秒程度を候補とし、実装時に調整する。

## 4. Thunderbird から直接計算する件数

次の件数は WIB API や WIB の SQLite を使用せず、Thunderbird が保持する対象 IMAP mailbox のメッセージ情報から計算する。

- 未着眼・未読
- 未着眼・既読
- 返信必要
- 見る・検討
- 注目
- 締切あり
- スケジュール調整
- 返信待ち
- 対応待ち
- 対応あり

最低限、現在の WIB と同じ条件を使用する。

```text
未着眼・未読
= 未読
AND スターなし
AND 一括処理なし
AND 旧一括処理タグなし

未着眼・既読
= 既読
AND スターなし
AND 一括処理なし
AND 旧一括処理タグなし

通常ワークフロー
= 対象タグあり
AND スターあり
```

ダッシュボード件数には WIB の `new_mail_lookback_days` と同じ期間制限を適用する。Thunderbird 作業ビュー自体を同じ期間に限定するかは別判断とし、現行どおり mailbox 全体を対象にする場合は件数との差を画面に明記する。

## 5. 件数更新と性能

画面表示のたびに mailbox 全体を無制限に走査しない。

- 初回は対象期間に限定してページ単位で集計する。
- 集計結果を Extension のローカルストレージへ保存する。
- 新着、既読状態、スター、タグ、移動、削除を契機に更新する。
- API・イベント差異がある場合は短い debounce 後の対象期間再集計を使用する。
- `件数を更新` ボタンで手動再集計できるようにする。
- 集計中は処理段階と処理済み件数を表示する。
- 集計中も Thunderbird の通常操作を長時間停止させない。

差分更新の複雑さや信頼性に問題がある場合は、初回実装ではイベントごとの対象期間再集計を採用し、実測後に最適化する。

## 6. WIB 接続なしで利用できる機能

次の操作は Thunderbird と Extension だけで実行する。

- 作業ビューを開く
- メールを読む
- スターを付ける、外す
- WIB タグを付ける、外す
- 返信、転送する
- 通常ワークフローを終了する
- Message-ID から元メールを開く

Thunderbird 上で行った変更は IMAP へ反映する。WIB は次回の通常同期時にメール・タグの現在状態を取り込む。WIB 用の更新処理をオフラインキューへ保存して後から再実行する仕組みは初回範囲に含めない。

## 7. WIB 接続中だけ利用できる機能

次は WIB API、SQLite または AI が必要なため、接続不可時は理由を表示して無効化する。

- 通常同期、全件再確認
- AI 初期分類と再判定
- 締切候補の抽出、登録、修正
- スケジュール調整支援の内部状態更新
- relation の参照・更新
- Record の保存・表示
- SQLite のみを正本とする情報の表示・更新

WIB が復旧した場合は自動的に接続中へ戻し、ページ全体の再読み込みを要求せず利用可能な導線を有効化する。

## 8. WIB API 案

### `GET /api/health`

Extension が WIB とバックエンドの利用可否を確認する。

```json
{
  "status": "ok",
  "version": "0.3.0",
  "api_version": 1,
  "database": "ok",
  "sync_running": false,
  "last_sync_at": "2026-08-29T10:30:00+09:00"
}
```

ヘルスチェック自体は IMAP 全件確認や AI 呼び出しを行わず、短時間で応答する。

### `GET /api/extension/bootstrap`

オンライン時に Extension が必要な初期情報をまとめて取得する候補 API とする。

- API 仕様バージョン
- WIB バージョン
- `new_mail_lookback_days`
- 対象 IMAP account / mailbox を解決するための情報
- 最終同期日時と同期状態
- WIB 専用情報の最終スナップショット

既存の `/api/sync-status` と `/api/thunderbird/imap-target` は互換性のため維持する。新しい bootstrap API を追加するか、既存 API を個別に呼ぶかは実装前に決める。

## 9. Extension のローカル保存

保存対象は必要最小限とする。

- WIB 接続先 URL
- `new_mail_lookback_days`
- 解決済み Thunderbird account / folder ID
- 最終接続成功日時
- Thunderbird 集計結果と集計日時
- WIB 専用件数の最終取得値と取得日時
- API 仕様バージョン

次は保存しない。

- IMAP password
- API token 等の credential
- SSH 情報
- メール本文

件名、差出人、Message-ID 等のメール単位キャッシュは初回実装では持たず、必要性が確認できた場合に保存範囲と保持期間を別途設計する。

## 10. 表示上の区別

情報の正本と鮮度を利用者が判断できるようにする。

- `Thunderbird 現在値`: Thunderbird のローカルメール状態から集計
- `WIB 現在値`: 接続中の WIB API から取得
- `WIB 最終取得値`: 接続できないため最後に成功した値を表示

最終取得値には日時を必ず表示する。Thunderbird がオフラインの場合、`Thunderbird 現在値`も最後に IMAP 同期した状態であることが分かる表示を検討する。

## 11. 初回実装の対象外

- 現在の WIB Web UI の廃止
- Active、締切、スケジュール調整、Record 等の全画面移植
- オフラインでの AI 判定
- WIB 更新操作のオフラインキューと後同期
- SQLite の Extension への複製
- 複数 Thunderbird profile 間の Extension キャッシュ同期
- メール本文・メール一覧全体の永続キャッシュ

## 12. 完了条件案

- WIB 接続中、確認中、一部利用不可、接続不可を区別して表示できる。
- WIB 停止中または SSH tunnel 切断中でも Thunderbird 由来の件数を表示できる。
- 件数から対応する Thunderbird 作業ビューを開ける。
- メールの既読、スター、タグを変更すると件数が更新される。
- `new_mail_lookback_days` とダッシュボード集計期間が一致する。
- WIB 専用機能は接続不可時に理由付きで無効になる。
- WIB 復旧後に自動的に接続中へ戻る。
- 対象期間に多数のメールがあっても Thunderbird の通常操作を長時間停止させない。
- credential やメール本文を Extension キャッシュへ保存しない。
- 自動テストと、接続中・WIB停止・SSH切断・復旧後の Thunderbird 実機確認を行う。

## 13. 実装前に決めること

### 今決める

- Thunderbird 由来情報と WIB 由来情報の責務境界
- 対象 mailbox の特定方法とオフライン時の再利用方法
- 集計条件と `new_mail_lookback_days` の一致
- 保存してよいデータと保存しないデータ
- 初回実装で利用可能にする操作

### 実装時に決める

- popup とダッシュボードタブの役割分担
- polling 間隔、timeout、debounce 時間
- イベント差分更新と対象期間再集計の使い分け
- 接続状態の細かな文言・色・配置
- bootstrap API を追加するか既存 API を組み合わせるか

### 将来でよい

- WIB Web UI 全体の Extension 移行
- オフライン操作の後同期
- 複数端末・profile 間同期
- メール一覧・本文のローカル永続キャッシュ
