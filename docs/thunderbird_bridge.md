# Thunderbird Bridge 詳細設計

この文書は `docs/design.md` を正本として、WIB Web UI と Thunderbird Extension の接続方法を補足する。

---

## 1. 責務

Thunderbird はメール業務の実行環境として、次を担当する。

- 未着眼メールの確認とスター付与
- 通常ワークフローのメール閲覧・返信・処理
- メール本文作成・送信・返信・転送
- アーカイブ
- WIB 作業ビュー
- WIB から Message-ID で指定されたメールを開く

WIB はダッシュボード、専用ワークフロー、判定保留、待機、Record 等の文脈を保持し、必要な Thunderbird 操作だけ Extension へ依頼する。

---

## 2. 対象 IMAP アカウント

WIB の `config.yaml` にある IMAP 設定を正本とする。

WIB Web は `/api/thunderbird/imap-target` で次だけを Extension へ渡す。

- `host`
- `port`
- `username`
- `mailbox`

password は返さない。

Extension は Thunderbird 内の IMAP アカウントから host / port / username が一致するものを解決し、設定された mailbox を作業対象とする。

---

## 3. Message-ID Bridge

WIB の元メール参照は Message-ID を正式な識別子とする。

WIB Web の元メール導線は、Message-IDの前後の`< >`を除いた`mid:` URIを主導線とする。Thunderbird内でクリックした場合はThunderbird標準のMessage-ID処理で直接開くため、Extensionによる全メール検索を通常操作には使わない。

Thunderbird内では、`mid:`で見つからない場合の予備操作として「見つからない場合は検索」も表示する。このボタンは従来どおり`data-wib-open-message-id`からExtensionの`workinbox-open-message`へMessage-IDを渡し、対象メールを検索してタブで開く。検索失敗時の理由はボタン上に表示する。Extensionが存在しない通常ブラウザでは予備ボタンを表示せず、OSに登録された`mid:`の処理へ委ねる。

予備検索では、通常の active メールは INBOX を基本対象とする。Record / 締切の元メールは `docs/design.md` の検索原則に従い、INBOX、次に元メール送信年月に対応する Archive を対象とする。

---

## 4. WIB 作業ビュー

WIB WebおよびExtension内ダッシュボードから `workinbox-open-work-view` を呼び、Thunderbird の WIB 専用作業タブを開く。

作業タブは同一タブを再利用し、WIB 設定の mailbox を表示する。

### 4.1 未着眼確認

未着眼の固定条件は次とする。

```text
スターなし
AND 一括処理なし
```

既存メール互換のため旧 keyword `wib-batch` も `一括処理` と同様に除外する。

Thunderbird 標準 WebExtension の Quick Filter だけでは `スターなし` を直接表現できないため、Extension の最小 Experiment API で Thunderbird の custom Mail View `WIB 未着眼` を作成・保存・適用する。

Custom Mail View の検索条件は次とする。

```text
Message Status is not Marked
AND Keywords does not contain wib-bulk
AND Keywords does not contain wib-batch
```

利用手順は次とする。

```text
WIB 未着眼
  ↓
未読 Quick Filter ON
  → 未着眼・未読を先に整理
  → 必要なメールへスターを付ける
  ↓
未読整理後に未読 Quick Filter OFF
  → 残ったメールを確認
```

WIB ダッシュボードの `未着眼・未読` は custom Mail View に未読 Quick Filter を重ねて開く。

`未着眼・既読` は同じ custom Mail View を未読 Quick Filter なしで開く。ダッシュボード上の件数自体は `スターなし AND 既読 AND 一括処理なし` を厳密に数える。Thunderbird 側では未読を先に整理する運用により、未読解除後の残りを既読整理として扱う。

### 4.2 通常ワークフロー

通常ワークフローは Thunderbird 標準 Quick Filter を使う。

- `返信必要`: `wib-answer AND ★`
- `見る・検討`: `wib-review AND ★`
- `注目`: `wib-watch AND ★`

未着眼 custom Mail View から通常ワークフローへ切り替える場合は custom Mail View を解除してから Quick Filter を適用する。

### 4.3 補助ビュー

次のビューも `対象タグ AND ★` で開ける。

- `締切あり`
- `スケジュール調整`
- `返信待ち`
- `対応待ち`
- `対応あり`

専用ワークフローの主な入口は WIB であり、これら Thunderbird ビューは補助的に扱う。

---

## 5. WIB Web からの導線

WIB Web のボタンに `data-wib-open-work-view` を付け、content script `workinbox_bridge.js` が次を行う。

1. `/api/thunderbird/imap-target` を取得する。
2. Extension background へ `workinbox-open-work-view` を送る。
3. background が対象 account / mailbox を解決する。
4. 未着眼、締切あり、スケジュール調整は除外条件を含む custom Mail View、その他は Quick Filter を適用する。
5. WIB 作業タブを前面にする。

ダッシュボードの最低限の直接導線は次とする。

- 未着眼・未読
- 未着眼・既読
- 返信必要
- 見る・検討
- 注目

`締切あり`の作業ビューは`締切登録済み`を除外する。`スケジュール調整`の作業ビューは`依頼済み`と`スケジュール対応済み`を除外し、ダッシュボード件数およびWIB Web一覧と処理対象を一致させる。

---

## 6. 専用ワークフローからのメール作成

専用ワークフローで支援者へ依頼する M2 は M1 への Reply ではなく、M1 を本文内転送した別スレッドのメールとして Thunderbird で作成する。元メールの内容を支援者へ提示しつつ、M1 の標準返信スレッドとは分離する。

```text
M1 起点メール
  ↓ WIB から Thunderbird compose
M2 新規メール
  X-WorkInBox-Origin-Message-ID: M1 Message-ID
```

M2 の送信成立後、Extension が M1 に `依頼済み` を付ける。

self-Cc の M2 が INBOX に届いた後の `対応待ち + ★` と relation 保存は TriageBox が担当する。

---

## 7. 通常ワークフローの1クリック終了

Thunderbirdで表示中のメールが `返信必要` / `見る・検討` / `注目` のいずれかを持つ場合、Extensionのメッセージ表示ボタンから通常ワークフローを終了できる。

1回の操作で、既存タグを保持したまま `一括処理` を追加し、スターを外す。通常ワークフロータグがないメールでは誤操作を防ぐため何も変更しない。

---

## 8. Extension 内部 API の境界

標準 WebExtension API で表現できる操作は標準 API を使う。

Thunderbird 内部 API が必要な処理は小さな Experiment API に隔離する。現在の WIB 作業ビューでは次を Experiment API が担当する。

- WIB 対象 IMAP account の server 情報取得
- WIB 作業タブのタイトル設定
- `WIB 未着眼` custom Mail View の作成・保存・適用・解除

未着眼 custom Mail View 以外の通常作業ビューは標準 `mailTabs.setQuickFilter()` を利用する。

---

## 9. 実機確認

Extension 変更後は note 側で repository を更新し、Thunderbird の Extension を再読み込みして確認する。

代表確認:

1. WIB ダッシュボードから `未着眼・未読` を開く。
2. `WIB 未着眼` 条件に加えて未読だけが表示される。
3. 必要なメールへスターを付けると未着眼一覧から外れる。
4. `未着眼・既読` を開くと未読 Quick Filter が外れ、残った未着眼メールを確認できる。
5. `返信必要` / `見る・検討` / `注目` を開くとそれぞれ `対象タグ + ★` だけになる。
6. どの作業ビューも WIB 設定の IMAP account / mailbox を対象にする。
7. 通常ワークフローのメールで終了ボタンを押すと、元タグを残して `一括処理` が付き、スターが外れる。

人工的なメールを多数作る必要はなく、実際の受信箱で代表ケースを確認する。

---

## 10. Extension内ダッシュボードとオフライン動作

Extensionは専用ダッシュボードタブを持ち、WIB Webとは別にThunderbirdの対象mailboxから次を集計する。

- 未着眼（合計と未読 / 既読の内訳）
- `返信必要` / `見る・検討` / `注目`
- 専用タグ、判定保留、待機タグの作業件数

未着眼の合計と未読 / 既読の内訳だけにWIB設定の`new_mail_lookback_days`を適用し、他の件数はmailbox全体を対象にする。集計はメッセージヘッダーだけをページ単位で読み、本文をキャッシュしない。WIB WebまたはExtensionダッシュボードの未着眼カードから作業ビューを開く場合は、Extensionのcustom Mail Viewにも同じ日数条件を渡す。通常ワークフロー等の作業ビューに期間制限は追加しない。

ExtensionはWIBの`/api/health`、`/api/extension/bootstrap`、既存`/api/sync-status`を使って接続状態と設定を確認する。取得済みのIMAP対象設定、lookback日数、直近集計結果はExtensionローカルストレージへ保存し、WIB停止中にも再利用する。password等のcredentialはAPI応答にもキャッシュにも含めない。

WIB停止中も作業ビュー、メール閲覧・返信、スター・タグ操作、通常終了は利用可能とする。AI、SQLite、relation、Record、専用ワークフロー更新はオンライン時だけWIB Webで行う。

Extensionダッシュボードの接続状態欄には通常同期ボタンを置く。`POST /api/sync`で既存のバックグラウンド同期を開始し、`/api/sync-status`で状態を追跡する。WIB接続不可時と同期実行中は押せないようにする。
