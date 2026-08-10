# Thunderbird Bridge 設計

この文書は、WorkInBox Web UI と Thunderbird Extension を接続し、WorkInBox から元メールへ戻るための共通ブリッジを定義する。

`docs/README.md` を設計文書の入口とし、この文書は Thunderbird 固有連携の詳細として位置づける。

---

## 1. 目的

WorkInBox はメールや締切の整理を行うが、メール本文そのものは Thunderbird で読む。

そのため WorkInBox の各画面から、対応する元メールへすぐ戻れることを重視する。

主な利用場面:

- 締切候補から元メールを開く
- 正式締切一覧から元メールを開く
- 判定保留メールから元メールを開く
- スケジュール調整対象メールを開く
- 返信待ち / 対応待ちの会話を確認する

この機構を機能ごとに個別実装せず、共通の `Open in Thunderbird` ブリッジとして提供する。

---

## 2. 責務分担

### FastAPI / Jinja2

- WorkInBox の Web UI を提供する。
- Application Service を呼ぶ。
- SQLite / IMAP / AI 等の業務ロジックへアクセスする。
- 元メールを開く際は Message-ID を Thunderbird 側へ渡す。

FastAPI 自体は Thunderbird API を直接使用しない。

### Thunderbird Extension

- WorkInBox Web UI を Thunderbird 内のタブで開く。
- WorkInBox タグ定義を Thunderbird に登録する。
- Message-ID を受け取り Thunderbird 内で該当メールを検索する。
- 該当メールを通常の message display で開く。
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

WorkInBox Web UI
     │
     │ Message-ID
     ▼
Thunderbird Extension Bridge
     │
     ▼
Thunderbird messages API
     │
     ▼
Message display
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
FastAPI page
    │
    │ open-message request
    ▼
Extension content/bridge script
    │ runtime messaging
    ▼
Extension background
    │ Thunderbird API
    ▼
Message display
```

WorkInBox ページから Message-ID を渡し、content script が Extension runtime messaging で background へ転送し、background が Thunderbird messages API を使って元メールを解決・表示する。

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
/calendar/deadlines.ics
/api/...
```

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

## 13. v0.2 PoC 結果

以下は実機で確認済みである。

1. Extension から WorkInBox Web UI を Thunderbird タブで開く。
2. WorkInBox 画面から `Thunderbird で元メールを開く` を実行する。
3. Message-ID を Extension background へ渡す。
4. Thunderbird 内で Message-ID を検索する。
5. 該当メールを通常の message display で単体表示する。
6. Archive 配下の Favorite 状態を列挙し、索引ポリシー候補をプレビューする。
7. Favorite 状態と Gloda indexing を手動同期する。

Conversation / スレッド表示への直接遷移は試行したが安定しなかったため、v0.2 では採用しない。

このブリッジは締切以外の画面でも共通利用する。

---

## 14. 非目標

Thunderbird Extension に以下を実装しない。

- AI 分類
- 締切抽出
- 締切の正本管理
- SQLite の直接操作
- IMAP ワークフロー判断
- FastAPI UI の再実装

Extension は Thunderbird 固有機能への薄い接着層に留める。
