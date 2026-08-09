# WorkInBox タグ・外部案件取り込み・将来データ管理メモ

この文書は、v0.2 のタグ設計を検討する中で出た議論を記録するための設計メモである。

現時点で確定している方針と、v0.2 以後に検討する将来案を分けて記載する。

---

## 1. Thunderbird タグ連携の基本方針

WorkInBox の作業タグは、Thunderbird からも人が直接付け外しできることを重視する。

Thunderbird ではタグをキーボードから操作できるため、日常的に人が修正するタグは数字キーで扱いやすい位置に置くことを想定する。

特に以下のタグは利用者が手動で修正する頻度が高いと考えられる。

- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`
- `判定保留`

WorkInBox 側では IMAP keyword を安定した識別子として扱い、Thunderbird 側では同じ key に対して日本語表示名と色を定義する構成を目指す。

Thunderbird には、既知の key を指定してタグ定義を作成・更新できる公式 API があるため、小さな Thunderbird MailExtension を用意し、複数 PC の Thunderbird プロファイルへ同じ WorkInBox タグ定義を登録する方式を採用候補とする。

ただし、WorkInBox 用 IMAP keyword の具体的な key 名、色、数字キー上の最終配置はまだ確定しない。

---

## 2. 参照タグ `重要`

既存運用では、アーカイブ後も後日参照する可能性があるメールに `重要` タグを付けている。

この用途は作業状態とは異なるため、WorkInBox では `重要` を新しい **参照タグ** として扱う方向とする。

### 性質

- `重要` は「今どの作業を行うか」を表す作業タグではない。
- アーカイブ後も保持してよい。
- スターの有無とは独立する。
- `一括処理` と共存してよい。
- `締切あり`、`回答必要`、`読む・検討` などとも共存してよい。

したがって、たとえば以下はすべて有効な状態とする。

- `重要` + `一括処理`
- `重要` + `読む・検討`
- `重要` + `回答必要`

現時点では参照タグは `重要` の 1 種類のみ追加する。

将来的に参照・保存用途のタグが必要になった場合は、作業タグとは別カテゴリとして拡張する。

---

## 3. Thunderbird のキーボード操作との共存

利用者は現在 `重要` タグを日常的に使っているため、WorkInBox 導入によって既存の操作感を壊さないことを重視する。

数字キーの配置案としては、たとえば以下のような構成が考えられる。

- `1`: `重要`
- `2`: `締切あり`
- `3`: `スケジュール調整`
- `4`: `回答必要`
- `5`: `読む・検討`
- `6`: `判定保留`

これは現時点では候補であり、最終仕様ではない。

また、WorkInBox は利用者が独自に作成した他の Thunderbird タグを勝手に削除・上書きしない。

---

## 4. 自分宛て備忘メールという入口

日常の仕事はメールだけから発生するとは限らない。

たとえば、以下のような経路から利用者自身の対応案件が発生する。

- LINE
- Microsoft Teams
- Slack
- 口頭での依頼
- その他の外部ツール

このような案件について、利用者が備忘のため **自分自身へメールを送る** 運用がある。

WorkInBox はこの運用を正式な入力経路として扱えるようにする。

### 基本的な役割分担

入口判定は TriageBox が担当する。

概念的には以下の流れとする。

```text
LINE / Teams / Slack / 口頭など
            ↓
       自分宛てメール
            ↓
         TriageBox
            ↓
   自分宛て備忘メールと判定
            ↓
       TrackingBox 対象
            ↓
       作業内容を分類
```

TriageBox は「差出人が自分である」という事実だけで処理先を決めてはいけない。

自分が送信したメールには少なくとも以下の種類がある。

1. **自分宛て備忘メール**
   - 外部ツールや口頭から発生した仕事をメールとして WorkInBox に取り込むためのもの。
   - 通常の TrackingBox 作業分類へ進める。

2. **相手へ送信したメールの自分宛てコピー等**
   - 相手からの回答を待つ目的であれば `返信待ち` の対象になり得る。

3. **支援者への依頼メール**
   - `対応待ち` の対象になる。

したがって、`From` が利用者自身であることだけを理由に `返信待ち` を付与しない。

TriageBox はメールの宛先、スレッド関係、既存の待機状態、内容等を用いて、自分発メールの役割を区別する必要がある。

### v0.2 での扱い

現時点の v0.2 では TrackingBox 対象となるスターは利用者が Thunderbird 上で付ける前提を維持する。

そのため、まずは自分宛て備忘メールが誤って `返信待ち` や別の特殊フローへ送られないことを重要とする。

将来 TriageBox がスター付与まで自動化する場合、自分宛て備忘メールは TrackingBox へ送る有力な自動スター候補となる。

---

## 5. メール以外の案件を WorkInBox に取り込む考え方

WorkInBox はタスク管理ツールではなく、利用者へ専用のタスク入力画面を要求しないという方針を維持する。

そのため、メール以外で発生した仕事についても、専用フォームを追加するより、利用者が慣れている「自分宛てメール」を入力口として利用できることに価値がある。

この方式により、外部ツールの種類に依存せず、最終的にメールという共通形式へ集約できる。

---

## 6. Thunderbird Extension の役割

タグ連携の検討から、Thunderbird MailExtension を WorkInBox と Thunderbird の **薄い接着層** として利用する案が有効であることが分かった。

Extension に業務ロジックや WorkInBox の正本データを持たせない。

WorkInBox の分類、状態管理、締切管理などの中核処理は従来どおり WorkInBox 側で行い、Extension は Thunderbird 固有 API が必要な処理だけを担当する。

### 想定する主な役割

1. **WorkInBox タグ定義の登録**
   - WorkInBox が決めた固定 key に対して、Thunderbird の日本語表示名と色を登録する。
   - 複数 PC の Thunderbird でも同じ key を利用できるようにする。

2. **WorkInBox Web UI を Thunderbird 内で開く**
   - WorkInBox の FastAPI + Jinja2 Web UI を作り直すのではなく、ローカルで稼働する Web UI を Thunderbird のタブから開けるようにする。
   - Thunderbird を日常の入口として維持しつつ、WorkInBox の整理画面へ移動できるようにする。

3. **WorkInBox の一覧から該当メールを Thunderbird で開く**
   - WorkInBox の Web UI でメールを選択した際、Extension が Thunderbird のメッセージ表示 API を使って該当メールを開く。
   - WorkInBox 側では Message-ID 等の安定した識別情報を使い、Thunderbird 固有 API 呼び出しは Extension 側へ寄せる。

概念的には以下の構成を想定する。

```text
Thunderbird
  ├─ メール閲覧・返信・タグ操作
  ├─ VTODO の閲覧
  └─ WorkInBox Web UI タブ
          ↓
Thunderbird Extension
  ├─ WIB タグ定義を登録
  ├─ WIB Web UI を開く
  └─ 指定メールを Thunderbird で開く
          ↓
WorkInBox
  ├─ FastAPI / Jinja2
  ├─ Application Service
  ├─ IMAP
  └─ SQLite
```

Extension は Thunderbird と WorkInBox の橋渡しだけを行い、可能な限り小さく保つ。

### 正本の扱いは変更しない

Extension を利用してもデータの正本方針は変更しない。

- **SQLite = WorkInBox 内部状態の正本**
- **VTODO = Thunderbird で閲覧・操作できる外部表現**

VTODO が Thunderbird 上で閲覧できることは UI 上の利点であるが、WorkInBox の内部状態の正本を VTODO へ移すことを意味しない。

同様に、Extension 自体も正本データを保持しない。

---

## 7. v0.2 以後の付加データ管理構想

タグ設計とは別に、将来的に WorkInBox が以下の付加情報を管理する案が出ている。

- 締切日時
- 概要
- XNote のような自由記述メモ
- `読む・検討` の結果
- AI 要約
- 再確認日
- その他の WorkInBox 独自情報

これらを SQLite のみに保存すると、DB 破損や移行時のリスクが高くなる。

そこで、SQLite 内のデータと意味的に対応する **交換可能な外部形式** を併用する構想を持つ。

### 例

- 締切データ: iCalendar / VTODO (`.ics`)
- 概要・メモ: XNote 互換形式、または将来決定する可搬形式
- WorkInBox 固有メタデータ: JSON 等

概念的には以下の構成を目標とする。

```text
IMAP
  ├─ メール本体
  └─ WorkInBox タグ

SQLite
  ├─ 締切
  ├─ 概要・メモ
  └─ WorkInBox 固有データ
       ⇅ import / export
交換形式
  ├─ deadlines.ics (VTODO)
  ├─ notes/...
  └─ metadata.json
```

### バックアップとしての意味

交換形式から SQLite を再構築できれば、単なる DB ファイルのコピーより復旧性が高くなる。

また、OneDrive 等へ交換形式やバックアップを複製することで、PC 故障時の復旧や将来の複数 PC 利用にもつなげられる。

ただし、SQLite ファイルそのものを OneDrive 上に置き、複数 PC から同時に直接書き込む方式は採用しない方向とする。

### 双方向交換

将来的には SQLite と外部形式を双方向で交換可能にすることを検討する。

ただし、複数 PC で同じデータを編集する場合は競合解決が必要になるため、v0.2 では実装しない。

まずは import / export と復旧可能性を優先し、同期・競合処理は後続バージョンで扱う。

---

## 8. v0.2 と将来バージョンの境界

### v0.2 で扱う

- IMAP タグの読み書き
- WorkInBox タグと Thunderbird 表示タグの安定した対応方法の検証
- Thunderbird Extension による WorkInBox タグ定義の登録検証
- 参照タグ `重要` の追加
- 自分宛て備忘メールを考慮した TriageBox 設計
- 自分発メールを一律に `返信待ち` とみなさないこと

### v0.2 以後または必要性に応じて扱う

- Extension から WorkInBox Web UI を Thunderbird 内タブで開く機能
- WorkInBox Web UI から指定メールを Thunderbird で開く連携
- 締切データの iCalendar / VTODO import / export
- XNote 等からの既存メモ取り込み
- WorkInBox 内の概要・メモ管理
- SQLite から可搬形式へのバックアップ
- 可搬形式から SQLite への再構築
- OneDrive 等を利用した複数 PC 間のデータ共有
- 双方向同期と競合解決

---

## 9. 未決事項

以下は今後決める。

- WorkInBox 用 IMAP keyword の正式な key 名
- 各タグの色
- Thunderbird 数字キーの最終割り当て
- `重要` の既存 Thunderbird keyword をそのまま利用するか、WorkInBox 用 key へ移行するか
- Thunderbird MailExtension の最低対応バージョン
- WorkInBox Web UI と Extension の連携方法
- Message-ID を使ったメールオープン連携の具体的な実装方法
- 自分宛て備忘メールを TriageBox がどの条件で自動判定するか
- 将来のメモ交換形式
- XNote 既存データの具体的な取り込み方法
