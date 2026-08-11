# Thunderbird Bridge 設計

この文書は、WorkInBox Web UI と Thunderbird Extension を接続し、WorkInBox から元メールや Thunderbird の作業ビューへ戻るための共通ブリッジを定義する。

`docs/README.md` を設計文書の入口とし、この文書は Thunderbird 固有連携の詳細として位置づける。

---

## 1. 目的

WorkInBox はメールや締切の整理を行うが、メール本文そのものは Thunderbird で読む。

そのため WorkInBox の各画面から、対応する元メールや作業対象メール一覧へすぐ戻れることを重視する。

主な利用場面:

- 締切候補から元メールを開く
- 正式締切一覧から元メールを開く
- 判定保留メールから元メールを開く
- スケジュール調整対象メールを開く
- 返信待ち / 対応待ちの会話を確認する
- `回答必要` 等の WIB 一覧から、WIB config が対象とする IMAP mailbox に Quick Filter を適用した専用作業ビューへ移動する

この機構を機能ごとに個別実装せず、共通の Thunderbird Bridge として提供する。

---

## 2. 責務分担

### FastAPI / Jinja2

- WorkInBox の Web UI を提供する。
- Application Service を呼ぶ。
- SQLite / IMAP / AI 等の業務ロジックへアクセスする。
- 元メールを開く際は Message-ID を Thunderbird 側へ渡す。
- 作業ビューを開くための IMAP 対象情報を `config.yaml` から提供する。
- `/api/thunderbird/imap-target` では `host` / `port` / `username` / `mailbox` のみを返し、IMAP password は返さない。

FastAPI 自体は Thunderbird API を直接使用しない。

### Thunderbird Extension

- WorkInBox Web UI を Thunderbird 内のタブで開く。
- WorkInBox タグ定義を Thunderbird に登録する。
- Message-ID を受け取り Thunderbird 内で該当メールを検索する。
- 該当メールを通常の message display で開く。
- WIB Web から対象 IMAP 情報を取得し、Thunderbird 内の対応アカウントを自動解決する。
- WIB 専用メールタブを 1 枚だけ作成・再利用し、解決した mailbox に指定された Quick Filter を適用する。
- 専用タブの表示名を現在の作業ビューに合わせて `WIB:回答必要` 等へ更新する。
- Archive フォルダの Favorite 状態を Global Search / Gloda の索引ポリシーへ反映する。

Extension に締切判定、AI 分類、SQLite 更新等の業務ロジックを持たせない。

### Application Service

- WorkInBox の業務ロジックを持つ。
- FastAPI / CLI 等から共通利用する。
- Thunderbird Extension へ依存しない。

---

## 3. 全体構成

```text
Thunderbird
  ├─ Mail UI
  ├─ Calendar / Tasks
  └─ WorkInBox Web UI tab
          │
          │ HTTP
          ▼
      FastAPI / Jinja2
          │
          ▼
   Application Service
      ├─ SQLite
      ├─ IMAP
      └─ AI

WorkInBox Web UI / API
     │
     ├─ Message-ID
     │      ▼
     │  Thunderbird Extension Bridge
     │      ▼
     │  Message display
     │
     └─ IMAP target + work view request
            ▼
        Thunderbird Extension Bridge
            ▼
        Thunderbird IMAP account resolution
            ▼
        configured mailbox
            +
        dedicated WIB mail tab
            +
        Quick Filter
```

FastAPI を Thunderbird Extension の内部へ移植しない。

Extension は、ローカルで稼働している FastAPI を利用する Thunderbird 専用アダプタとする。

---

## 4. WorkInBox Web UI の開き方

Extension のボタン等から、ローカルで稼働する WorkInBox Web UI を Thunderbird 内のタブで開く。

例:

```text
http://127.0.0.1:8000/
```

利用者からは Thunderbird 内の 1 タブとして WorkInBox を利用できるようにする。

ただしページの実体は FastAPI / Jinja2 が生成する通常の Web UI である。

これにより、ブラウザ用 UI と Thunderbird 用 UI を二重実装しない。

---

## 5. Message-ID を共通リンクキーとする

WorkInBox は元メールとの論理的な関連に Message-ID を使用する。

例:

```text
source_message_id = <abc123@example.com>
```

Thunderbird 内部の一時的な message id や folder UID を、長期的な論理リンクとして SQLite に保存しない。

メールが月別アーカイブ等で別フォルダへ移動しても、Message-ID を使って Thunderbird 側で現在位置を再解決する。

---

## 6. 元メールを開く基本フロー

```text
WorkInBox 画面
    ↓
[Thunderbird で元メールを開く]
    ↓
source_message_id を取得
    ↓
Extension Bridge へ Message-ID を送る
    ↓
Thunderbird messages API で headerMessageId を検索
    ↓
該当 MessageHeader を取得
    ↓
通常の message display で単体表示
```

WorkInBox は「この Message-ID を開く」という依頼だけを行い、Thunderbird 内での検索方法や表示方法は Extension に閉じ込める。

この基本フローは実機 PoC で確認済みである。

---

## 7. Web UI と Extension 間のブリッジ

FastAPI から配信された通常の Web ページは Thunderbird Extension API を直接呼べない。

そのため、Web UI と Extension background 間に薄いブリッジを置く。

実装構成:

```text
FastAPI page / API
    │
    │ open-message / IMAP target
    ▼
Extension content/bridge script or popup
    │ runtime messaging
    ▼
Extension background
    │ Thunderbird API
    ▼
Message display / dedicated WIB mail tab + Quick Filter
```

作業ビューを開く際は Extension が `/api/thunderbird/imap-target` から WIB config の IMAP 対象情報を取得し、background へビュー種別とともに渡す。

責務境界を維持し、FastAPI 側へ Thunderbird 固有ロジックを持ち込まない。

---

## 8. Conversation / スレッド表示

第一段階の必須条件は Message-ID から正確に元メールを単体表示できることであり、これは実機で確認済みである。

その後、Thunderbird の 3 ペイン / スレッド表示へ直接遷移する試行を行ったが、実機で安定して動作しなかったため採用しなかった。

したがって v0.2 では次を確定方針とする。

1. `Message-ID -> MessageHeader` の解決を共通基盤とする。
2. `MessageHeader -> 通常の message display` を v0.2 の標準表示とする。
3. Conversation / スレッド表示への直接遷移は v0.2 の必須成功条件にしない。
4. 将来再検討する場合も、Message-ID 解決とは分離した追加アダプタとして扱う。

Global Search / Gloda の索引状態が不完全でも、Message-ID から元メールを特定して通常表示へ遷移できることを優先する。

---

## 9. 締切登録支援との連携

締切候補画面では、候補ごとに元メールを開けるようにする。

例:

```text
論文投稿締切
2026-09-15

[登録する]
[修正する]
[登録しない]
[Thunderbird で元メールを開く]
```

締切の登録・修正・却下は FastAPI / Application Service が担当する。

`元メールを開く` だけが Thunderbird Bridge を利用する。

正式締切一覧でも同じ仕組みを再利用する。

---

## 10. Context との関係

v0.2 では WorkInBox 内部にメールスレッド / 案件 Context を導入しない。

締切と起点メールの関連は Message-ID 単位とする。

必要な周辺文脈は Thunderbird のメール表示で確認する。

この設計により、WorkInBox が独自のメールスレッド閲覧 UI を作る必要を減らせる。

将来 Context が必要になった場合も、Message-ID を基礎情報として利用できる。

---

## 11. FastAPI の役割拡張

FastAPI は UI サーバであると同時に、必要に応じて WorkInBox の機械向け API と ICS 提供を担う。

概念例:

```text
/
/pending
/deadlines
/deadlines.ics
/api/thunderbird/imap-target
```

`/api/thunderbird/imap-target` は Thunderbird Extension が WIB の対象 IMAP アカウントを自動解決するための機械向け API である。

返却するのは `host` / `port` / `username` / `mailbox` のみとし、password は公開しない。

ただし UI route、JSON API、ICS endpoint のいずれからも、業務ロジックは Application Service を利用する。

FastAPI route に SQLite / IMAP の業務ロジックを直接埋め込まない。

---

## 12. Archive の Global Search / Gloda 索引ポリシー

大量の古い Archive フォルダをすべて Global Search の索引対象にすると、`global-messages-db.sqlite` の再構築や維持に長い時間を要する可能性がある。

一方で、現在も頻繁に参照する Archive は Global Search から利用できる方が便利である。

そのため Archive 配下では、**Thunderbird の Favorite 状態を「現在も Global Search 対象にしたい Archive」を示す利用者入力として利用する**。

基本ポリシー:

```text
Archive 配下
    │
    ├─ Favorite = ON  → Gloda indexing ON
    └─ Favorite = OFF → Gloda indexing OFF
```

年数やフォルダ名から自動判定する方式を標準ルールにはしない。

利用者が Thunderbird の既存 UI で Favorite を付け外しすることで、検索対象として残したい Archive を選択できるようにする。

### 標準 API と Experiment API の分離

Favorite 状態の取得・変更など、標準 MailExtension API で実装可能な処理は標準 API を使用する。

Gloda のフォルダ単位の indexing ON / OFF は標準 MailExtension API で直接操作できないため、その処理だけを最小の Experiment API に閉じ込める。

Experiment API に WorkInBox の業務ロジックを持たせない。

Experiment 層は Thunderbird 内部の Gloda 設定を操作するための小さなアダプタに限定する。

### 初期実装と実機確認結果

v0.2 の初期実装では Favorite 状態変更への常時自動追随は行わず、利用者が明示的に実行する手動同期とする。

実機 PoC では次を確認済みである。

- Archive 配下の Favorite 状態を列挙できる。
- Favorite と現在の indexing 状態を比較し、変更予定をプレビューできる。
- Favorite ON = indexing ON、Favorite OFF = indexing OFF のポリシーを手動同期できる。

同期確認 UI は popup が閉じないインライン確認方式とし、直近の診断結果を保持して再表示できるようにした。

将来、動作の安定性と必要性が確認できた場合は Favorite 状態変更への自動追随を検討する。

### Message-ID Bridge との役割分担

Gloda 対象外の古い Archive であっても、WorkInBox の元メール参照を失わないことを重視する。

```text
Global Search
    = 普段検索する Favorite Archive を中心に利用

Message-ID Bridge
    = Gloda 対象外を含め、必要な元メールへ戻る経路
```

したがって、Gloda の索引対象を絞ることと、WorkInBox からメール正本へ戻れることは独立して設計する。

---

## 13. Quick Filter 作業ビュー

WorkInBox はメールを独自 UI に閉じ込めず、日常のメール処理は Thunderbird のメール一覧を活用する。

WIB の `回答必要`、`締切あり` 等の現在作業を確認するときは、通常利用中のメールタブへ Quick Filter を上書きしない。WIB 専用のメールタブを 1 枚だけ作成し、そのタブを作業ビュー間で再利用する。

### 対象 IMAP アカウント

WIB 作業ビューの対象 IMAP 情報は `config.yaml` の `imap` 設定を正本とする。

Extension の popup で対象アカウントを手動選択・保存しない。

作業ビューを開くたびに Extension は FastAPI の `/api/thunderbird/imap-target` から以下を取得する。

- `host`
- `port`
- `username`
- `mailbox`

password は取得しない。

Extension は Thunderbird の IMAP アカウントを列挙し、各アカウントの incoming server 情報を `imapAccounts` Experiment で読み取って照合する。

基本照合は `host + port + username` とする。username は Thunderbird と WIB config の表現差を吸収するため、完全一致に加えて、一方が `user@example.jp`、もう一方が `user` の場合はローカル部一致を候補として認める。

一致候補が 0 件または複数件の場合は、別アカウントへ自動フォールバックせずエラーにする。

アカウント解決後は WIB config の `mailbox` を対象フォルダとして使用する。通常は `INBOX` を想定する。

これにより WIB config が対象メール環境の正本となり、Extension 側に同じ対象アカウント設定を二重保持しない。

### 基本フロー

```text
Extension popup
    ↓
作業ビューを選択
    ↓
GET /api/thunderbird/imap-target
    ↓
WIB config の host / port / username / mailbox を取得
    ↓
Thunderbird IMAP account を自動照合
    ↓
config で指定された mailbox を解決
    ↓
WIB 専用メールタブを取得
    ├─ 既存なら再利用
    └─ 閉じられていれば新規作成
    ↓
Quick Filter Bar を表示
    ↓
スター付き AND 対応 WIB タグを適用
    ↓
専用タブを active にする
    ↓
タブ名を WIB:<作業ビュー名> に更新
```

WIB 専用タブを閉じた場合は、次回の作業ビュー表示時に新しい専用メールタブを作成する。

通常の INBOX タブに利用者が設定している `未読`、`添付あり` 等の Quick Filter は変更しない。

### 作業ビュー

v0.2 の初期実装で次の 6 種類を提供する。

- `回答必要` = `wib-answer` AND スター付き → `WIB:回答必要`
- `締切あり` = `wib-deadline` AND スター付き → `WIB:締切あり`
- `スケジュール調整` = `wib-schedule` AND スター付き → `WIB:スケジュール調整`
- `読む・検討` = `wib-review` AND スター付き → `WIB:読む・検討`
- `返信待ち` = `wib-waiting-reply` AND スター付き → `WIB:返信待ち`
- `対応待ち` = `wib-waiting-action` AND スター付き → `WIB:対応待ち`

同じ WIB 専用タブの Quick Filter 条件とタブ名だけを切り替える。

Quick Filter の具体的な Thunderbird API 引数は Extension 側のプリセットとして定義し、FastAPI 側から直接渡さない。

### 標準 API と Experiment API

作業ビューの主要処理は標準 MailExtension API で実装する。

- 対象アカウントの列挙・取得: `accounts`
- WIB 専用メールタブの作成・再利用: `mailTabs`
- mailbox 表示: `mailTabs.update()`
- Quick Filter 適用: `mailTabs.setQuickFilter()`
- タブの active 化: `tabs.update()`

標準 API だけでは必要情報を扱えない箇所を小さな Experiment API に限定する。

- `imapAccounts`: 指定した Thunderbird account id の incoming server から `type` / `hostname` / `username` / `port` を読み取る。
- `tabTitle`: WIB 専用メールタブの表示タイトルを変更する。

`imapAccounts` はアカウント選択ロジックを持たず、server情報を読むだけのアダプタとする。実際の照合判断は Extension background 側で行う。

`tabTitle` は指定された Thunderbird タブの表示タイトルを更新するだけのアダプタとし、WIB のビュー判定や業務状態を持たない。

どちらも Thunderbird 内部 API / UI 構造に依存するため、Thunderbird 更新時は互換性を個別に確認する。

### スターとの役割分担

Quick Filter には Thunderbird の「返信済み」状態を直接条件にできないため、WIB の現在注目対象を示すスターを AND 条件に利用する。

たとえば `回答必要` メールについて、利用者が Thunderbird で返信を完了した後、WIB の同期・TriageBox がそのメールを現在注目対象から外すべきと判断したらスターを外す。

`wib-answer` タグが履歴として残っていても、スターが外れることで `回答必要 = wib-answer AND スター付き` の作業ビューから自然に除外される。

この方式により、Thunderbird 標準の返信済みフラグを Quick Filter から直接検索できなくても、WIB の状態遷移と Thunderbird の作業ビューを一致させられる。

### 検索フォルダーとの関係

利用者が手動で作成した検索フォルダーは引き続き活用できる。

WIB の標準作業ビューについては、検索フォルダーを自動生成せず、実機で成立した専用メールタブ + Quick Filter を v0.2 の基本方式とする。

任意条件の検索フォルダー自動生成が本当に必要になった場合にのみ、別の Experiment API 等を検討する。

---

## 14. v0.2 PoC 結果

以下は実機で確認済みである。

1. Extension から WorkInBox Web UI を Thunderbird タブで開く。
2. WorkInBox 画面から `Thunderbird で元メールを開く` を実行する。
3. Message-ID を Extension background へ渡す。
4. Thunderbird 内で Message-ID を検索する。
5. 該当メールを通常の message display で単体表示する。
6. Archive 配下の Favorite 状態を列挙し、索引ポリシー候補をプレビューする。
7. Favorite 状態と Gloda indexing を手動同期する。
8. FastAPI の `/api/thunderbird/imap-target` から WIB config の IMAP 対象情報を取得する。
9. Thunderbird 内の対応 IMAP アカウントを利用者選択なしで自動解決する。
10. 通常のメールタブを変更せず、WIB 専用メールタブを作成して再利用する。
11. 同じ専用タブ上で 6 種類の `WIB タグ AND スター付き` Quick Filter を切り替える。
12. 作業ビュー切替に合わせてタブ名を `WIB:回答必要` 等へ更新する。
13. WIB 専用タブを閉じた場合、次回利用時に専用タブを再作成する。

Conversation / スレッド表示への直接遷移は試行したが安定しなかったため、v0.2 では採用しない。

Quick Filter 作業ビューは実装済みであり、WIB config からの対象アカウント自動解決・専用タブ方式・6 ビュー切替・タブ名追随まで実機で確認済みである。

このブリッジは締切以外の画面でも共通利用する。

---

## 15. 非目標

Thunderbird Extension に以下を実装しない。

- AI 分類
- 締切抽出
- 締切の正本管理
- SQLite の直接操作
- IMAP ワークフロー判断
- FastAPI UI の再実装

Extension は Thunderbird 固有機能への薄い接着層に留める。