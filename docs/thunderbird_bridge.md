# Thunderbird Bridge 設計

この文書は、WorkInBox Web UI と Thunderbird Extension を接続し、WorkInBox から元メールや Conversation 表示へ戻るための共通ブリッジを定義する。

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
- 該当メール、または可能であれば Conversation 表示を開く。

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
Message / Conversation view
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
メール表示 / Conversation 表示
```

WorkInBox は「この Message-ID を開く」という依頼だけを行い、Thunderbird 内での検索方法や表示方法は Extension に閉じ込める。

---

## 7. Web UI と Extension 間のブリッジ

FastAPI から配信された通常の Web ページは Thunderbird Extension API を直接呼べない。

そのため、Web UI と Extension background 間に薄いブリッジを置く。

想定構成:

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
Message / Conversation
```

具体的な通信方式は実装時に最小構成で検証する。

候補:

- WorkInBox ページへ Extension の content script を注入する。
- Web ページ側から `window.postMessage` 等で Message-ID を渡す。
- content script が Extension runtime messaging で background へ転送する。
- background が Thunderbird messages API を呼ぶ。

通信方式の詳細より、責務境界を維持することを優先する。

---

## 8. Conversation 表示

第一段階では Message-ID から正確に元メールを開けることを必須とする。

その後、Thunderbird 128 / 140 系で利用可能な方法を確認し、可能であれば同じ Message-ID を起点に Conversation 表示へ遷移する。

Conversation 表示の実装方法は Thunderbird API / UI のバージョン依存性があるため、標準 messages API による Message-ID 解決と分離する。

設計上は次の 2 段階とする。

1. `Message-ID -> MessageHeader` の解決
2. `MessageHeader -> Message / Conversation UI` の表示

1 は共通基盤、2 は Thunderbird バージョンごとのアダプタとして扱えるようにする。

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

必要な周辺文脈は Thunderbird のメール表示 / Conversation 表示で確認する。

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

## 12. v0.2 での実装優先順位

締切登録支援全体を実装する前または並行して、次の小さな実証を行う価値がある。

1. Extension から WorkInBox Web UI を Thunderbird タブで開く。
2. WorkInBox のテスト画面に `Thunderbird で元メールを開く` を置く。
3. Message-ID を Extension background へ渡す。
4. Thunderbird 内で Message-ID を検索する。
5. 該当メールを表示する。
6. 可能であれば Conversation 表示へ拡張する。

このブリッジが成立すれば、締切以外の画面でも共通利用する。

---

## 13. 非目標

Thunderbird Extension に以下を実装しない。

- AI 分類
- 締切抽出
- 締切の正本管理
- SQLite の直接操作
- IMAP ワークフロー判断
- FastAPI UI の再実装

Extension は Thunderbird 固有機能への薄い接着層に留める。
