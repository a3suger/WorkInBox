# Thunderbird タグの導入前バックアップと復元

## 1. 目的

WorkInBox は Thunderbird に WorkInBox 用タグ定義を追加する。

その際、将来 WorkInBox の利用を停止した場合でも、**WorkInBox 導入前の Thunderbird タグ定義へ戻せること**を重視する。

この文書では、次を扱う。

- WorkInBox 導入前の Thunderbird タグ定義を保存する方法
- WorkInBox タグ導入後に何が変わるか
- WorkInBox 利用停止時に元のタグ定義へ戻す方法
- Thunderbird のタグ定義と、メール上の IMAP keyword の違い
- 旧 WorkInBox タグ定義の扱い
- より強い保険として Thunderbird プロファイル全体を退避する方法

この仕組みは、WorkInBox が既存 Thunderbird 環境を一方的に置き換えず、利用者が元へ戻れるようにするためのものである。

---

## 2. Thunderbird のタグは2つの層に分けて考える

Thunderbird のタグ連携では、次の2つを区別する。

### A. Thunderbird のタグ定義

Thunderbird がローカルに持つタグの定義である。

主に次の情報を持つ。

- key
- 表示名
- 色
- 並び順に関係する情報

WorkInBox Extension はこの層へ `wib-*` のタグ定義を追加する。

### B. 各メールに保存される IMAP keyword

実際にメールへタグを付けると、IMAP サーバー上のメールに keyword が保存される。

例:

```text
wib-deadline
```

Thunderbird のタグ定義を削除しても、各メールに付いている IMAP keyword が自動的に消えるとは限らない。

したがって、WorkInBox の利用を停止するときは、

1. Thunderbird のタグ定義を元へ戻すこと
2. 必要に応じてメール上の `wib-*` keyword を削除すること

を別々に考える。

---

## 3. WorkInBox 導入前に保存するもの

13個の WorkInBox タグを Thunderbird へ登録する前に、現在のタグ定義を保存する。

最低限、次を保存する。

```text
key
表示名
色
ordinal / 並び順に関係する値
```

保存形式は JSON とする。

例:

```json
[
  {
    "key": "$label1",
    "tag": "重要",
    "color": "#FF0000",
    "ordinal": ""
  }
]
```

実際の内容は、その Thunderbird プロファイルに存在するタグをすべて保存する。

ファイル名の例:

```text
thunderbird-tags-before-workinbox.json
```

可能であれば保存日時と Thunderbird バージョンも併記する。

---

## 4. Extension に持たせるバックアップ機能

WorkInBox の Thunderbird Extension は、WorkInBox タグを初めて追加する前に現在の Thunderbird タグ一覧を取得し、導入前スナップショットを作成する。

概念的には Thunderbird のタグ API からタグ一覧を取得し、JSON 化する。

重要なのは、**WorkInBox タグを追加した後の状態ではなく、追加する直前の状態を保存すること**である。

また、初回バックアップを後から自動上書きしない。

利用中に Thunderbird のタグを変更した場合は、必要に応じて別の日時付きバックアップを作れるようにする。

例:

```text
thunderbird-tags-before-workinbox.json
thunderbird-tags-backup-2026-08-09.json
```

---

## 5. バックアップをどこに置くか

Extension 内部ストレージだけに保存すると、Extension 削除時に失う可能性がある。

そのため、復元用スナップショットは利用者が通常のファイルとして保管できる形を優先する。

候補:

- WorkInBox のデータディレクトリ
- 利用者が指定したバックアップフォルダ
- OneDrive 等へバックアップする WorkInBox 用ディレクトリ

少なくとも「Extension を削除してもバックアップが残る」場所に保存する。

---

## 6. さらに安全にするための Thunderbird プロファイル全体バックアップ

タグ定義 JSON は、タグだけを戻すための軽量バックアップである。

より強い保険として、WorkInBox 導入前に Thunderbird プロファイル全体を一度コピーしておくことを推奨する。

このバックアップは、タグ以外の Thunderbird 設定まで含めて元の状態へ戻したい場合に使う。

運用上は、次の2段構成とする。

```text
通常の復元
  → タグ定義 JSON を利用

重大な問題が起きた場合
  → Thunderbird プロファイル全体のバックアップを利用
```

プロファイル全体のバックアップは WorkInBox が自動的に直接変更・復元する対象にはせず、利用者向けの安全策として扱う。

---

## 7. WorkInBox 導入後に変更されるもの

WorkInBox Extension は、既存タグを全削除して置き換える方式を採らない。

既存 Thunderbird タグを保持したまま、WorkInBox 用の `wib-*` タグ定義を追加する。

現行 `docs/design.md` に対応するタグ定義は次のとおり。

```text
wib-watch             注目
wib-deadline          締切あり
wib-schedule          スケジュール調整
wib-answer            返信必要
wib-review            見る・検討
wib-pending           判定保留
wib-deadline-done     締切登録済み
wib-schedule-done     スケジュール対応済み
wib-waiting-reply     返信待ち
wib-waiting-action    対応待ち
wib-action-ready      対応あり
wib-requested         依頼済み
wib-bulk              一括処理
```

WorkInBox は利用者独自のタグを勝手に削除・改名・上書きしない。

`重要` は WorkInBox の現行タグ体系では使用しない。

---

## 8. WorkInBox 利用停止時の復元手順

WorkInBox を利用しなくなった場合は、次の順序を基本とする。

### 手順1: WorkInBox の自動処理を停止する

先に WorkInBox 本体と Extension の自動処理を停止し、復元中に再びタグが追加されないようにする。

### 手順2: 導入前バックアップを確認する

`thunderbird-tags-before-workinbox.json` を開き、導入前タグが保存されていることを確認する。

### 手順3: WorkInBox の Thunderbird タグ定義を削除する

Thunderbird 側から WorkInBox が追加した `wib-*` タグ定義を削除する。

この段階では、メール上の IMAP keyword はまだ触らない。

### 手順4: 導入前のタグ定義を復元する

JSON に保存されている key、表示名、色などを使って、導入前の Thunderbird タグ定義を再作成または修正する。

特に、WorkInBox 導入時に既存タグを変更した場合は元の値へ戻す。

### 手順5: Thunderbird 上で見た目を確認する

次を確認する。

- 導入前のタグが存在する
- 表示名が正しい
- 色が正しい
- 必要なタグ順序が戻っている
- WorkInBox 用タグ定義が不要に残っていない

---

## 9. メール上の `wib-*` keyword をどうするか

Thunderbird のタグ定義を削除しても、メールに保存された `wib-*` keyword は IMAP サーバー上に残る可能性がある。

これはメールデータを壊しているわけではないが、WorkInBox を完全に撤去したい場合は削除対象になる。

### 選択肢A: 残しておく

WorkInBox を一時的に停止するだけなら、keyword を残してもよい。

将来同じ key のタグ定義を再登録すれば、再びタグとして認識できる可能性がある。

### 選択肢B: WorkInBox keyword を削除する

完全に WorkInBox の利用を終了するなら、IMAP 上の `wib-*` keyword をメールから削除する。

この処理では、WorkInBox が管理する keyword だけを対象とする。

```text
wib-*
```

標準 IMAP flag や利用者独自タグには触れない。

また、FLAGS 全体の置換は行わず、対象 keyword だけを個別に削除する。

---

## 10. 旧 WorkInBox keyword の扱い

旧実装では次の keyword を使用していた。

```text
wib-important
wib-batch
```

現行設計では `重要` を使用しないため、`wib-important` を `注目` へ自動変換しない。両者は意味が異なる。

`wib-batch` は `一括処理` の旧 keyword であり、新規書き込みは `wib-bulk` を使用する。既存メール上の `wib-batch` は移行時に破壊的に削除しない。WorkInBox 本体は既存 `wib-batch` を `一括処理` として読み取れるよう互換性を持たせる。

Extension のタグ登録では旧 `wib-important` / `wib-batch` の Thunderbird タグ定義を整理して現行13タグを登録するが、メール上の IMAP keyword 自体は削除しない。

---

## 11. 複数 PC の場合

Thunderbird を複数 PC で利用する場合、タグ定義は各 Thunderbird プロファイルごとに存在する。

そのため、導入前バックアップも原則として PC / プロファイル単位で取得する。

例:

```text
PC-A-thunderbird-tags-before-workinbox.json
PC-B-thunderbird-tags-before-workinbox.json
```

WorkInBox Extension が同じ `wib-*` 定義を各 PC へ登録しても、元々存在していたローカルタグ構成が同じとは限らないためである。

---

## 12. 実装チェックリスト

13タグを本格導入する際は、次を確認する。

- [ ] 現在の Thunderbird タグ一覧を取得できる
- [ ] key / 表示名 / 色 / 並び順情報を保存できる
- [ ] 導入前スナップショットを JSON として残せる
- [ ] 初回スナップショットを自動上書きしない
- [ ] Thunderbird プロファイル全体のバックアップ方法を利用者が確認できる
- [ ] WorkInBox タグだけを追加できる
- [ ] 既存タグを勝手に変更しない
- [ ] 旧 WorkInBox タグ定義を整理してもメール上の旧 keyword を破壊的に削除しない
- [ ] 復元時に WorkInBox タグ定義だけを削除できる
- [ ] バックアップから既存タグ定義を復元できる
- [ ] 必要ならメール上の `wib-*` keyword だけを削除できる

---

## 13. 基本方針

WorkInBox の Thunderbird 連携では、次を原則とする。

> WorkInBox を導入する前の Thunderbird 環境を記録し、WorkInBox の利用をやめても元へ戻せるようにする。

そのため、13タグの本格登録を行う前に、まず Thunderbird タグ定義のバックアップを確保する。
