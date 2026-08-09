# WorkInBox タグを Thunderbird で利用できるかの確認テスト

## 1. 目的

このテストの目的は、**WorkInBox が先に決めたタグを Thunderbird でも同じタグとして利用できるか**を確認することである。

今回確認したい構成は次のとおり。

```text
WorkInBox がタグを定義する
  key: wib-deadline
  表示名: 締切あり
  色: （テスト用の色）
        ↓
Thunderbird に同じ key のタグ定義を登録する
        ↓
Thunderbird で「締切あり」として表示・付与・解除できる
        ↓
IMAP 上には wib-deadline が保存される
        ↓
WorkInBox からも同じ wib-deadline を読み書きできる
```

つまり、**Thunderbird が作ったタグを WorkInBox が調べて合わせるテストではない**。

WorkInBox がタグの key を決め、その key を Thunderbird に登録できることを先に確認する。

この方針は `docs/design_notes_tags_and_external_intake.md` に基づく。

---

## 2. テストの考え方

最初から全タグを作らない。

まず `締切あり` 1個だけを使い、次の一連の流れが成立するかを確認する。

1. WorkInBox 側で固定 key を決める。
2. Thunderbird の公式 API を使って、その key の表示タグを登録する。
3. Thunderbird からそのタグを付ける。
4. IMAP 上に同じ key が保存されることを確認する。
5. Thunderbird からタグを外すと、IMAP 上から同じ key が外れることを確認する。
6. WorkInBox から同じ key を付けた場合、Thunderbird 上で `締切あり` と表示されることを確認する。
7. WorkInBox から外した場合、Thunderbird 上でも外れることを確認する。

ここまで成功したら、他の WorkInBox タグへ展開する。

---

## 3. 最初のテストタグ

最初の検証には `締切あり` を使う。

テスト用定義:

| 項目 | 値 |
| --- | --- |
| WorkInBox 表示名 | `締切あり` |
| WorkInBox key | `wib-deadline` |
| Thunderbird 表示名 | `締切あり` |
| 色 | テスト時に決定 |

`wib-deadline` はこの相互運用テスト用の key とする。

このテストが成功した後、全タグの正式 key をまとめて確定する。

---

## 4. Thunderbird 側のテスト用アドオン

Thunderbird には、既知の key を指定してメッセージタグを作成できる公式 API がある。

そのため、このテストでは **最小の Thunderbird MailExtension** を作る。

このアドオンの役割は WorkInBox 本体を Thunderbird 内で動かすことではない。

役割は1つだけである。

```text
WorkInBox が決めたタグ定義を
Thunderbird のローカルタグ定義へ登録する
```

最初のテストでは、アドオンが以下の1タグだけを登録すればよい。

```text
key      = wib-deadline
表示名   = 締切あり
color    = テスト用の色
```

Thunderbird の公式 `messages.tags` API を利用する。

想定する処理は概念的には次のようになる。

```javascript
messenger.messages.tags.create(
    "wib-deadline",
    "締切あり",
    "#......"
)
```

実際の manifest、permission、API 呼び出し方法は、使用する Thunderbird バージョンに合わせて実装時に確認する。

---

## 5. テスト1: Thunderbird に WIB タグを登録できるか

### 手順

1. テスト用 MailExtension を Thunderbird に読み込む。
2. `wib-deadline` / `締切あり` のタグ定義を登録する。
3. Thunderbird のタグ一覧を開く。
4. `締切あり` が表示されることを確認する。
5. Thunderbird を再起動する。
6. 再起動後も `締切あり` が利用可能であることを確認する。

### 成功条件

- WorkInBox が指定した `wib-deadline` という key で Thunderbird のタグ定義を作れる。
- Thunderbird 上では人向けの表示名 `締切あり` として利用できる。

この段階で登録できない場合、IMAP のテストには進まない。

---

## 6. テスト2: Thunderbird で付けた WIB タグが IMAP に保存されるか

### テストメール

本番メールではなく、自分宛てのテストメールを1通用意する。

対象メールは INBOX に置いておく。

### 手順

1. Thunderbird でテストメールを選択する。
2. WorkInBox アドオンで登録した `締切あり` を付ける。
3. Thunderbird の IMAP 同期を待つ。
4. WorkInBox の診断コマンドで FLAGS を確認する。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

または:

```bash
python -m workinbox.imap_debug --config config.yaml --uid 12345
```

### 期待する結果

FLAGS に次の keyword が見える。

```text
wib-deadline
```

重要なのは、Thunderbird が別の key を生成するのではなく、**WorkInBox が指定した `wib-deadline` がそのまま IMAP keyword として使われること**である。

---

## 7. テスト3: Thunderbird で WIB タグを外せるか

### 手順

1. Thunderbird でテストメールから `締切あり` を外す。
2. IMAP 同期を待つ。
3. 再度診断コマンドを実行する。

### 成功条件

FLAGS から `wib-deadline` が消える。

これにより、Thunderbird 上の付与・解除と IMAP keyword の付与・解除が同じ状態として扱えることを確認する。

---

## 8. テスト4: WorkInBox から付けたタグを Thunderbird が認識するか

これは v0.2 の IMAP タグ書き込み機能を実装した後に行う。

### 手順

1. Thunderbird では対象メールから `締切あり` を外しておく。
2. WorkInBox から対象メールへ `wib-deadline` を IMAP keyword として追加する。
3. Thunderbird を同期する。
4. Thunderbird 上でメールに `締切あり` が付いていることを確認する。

### 成功条件

```text
WorkInBox
  wib-deadline を追加
        ↓
IMAP
  wib-deadline
        ↓
Thunderbird
  締切あり と表示
```

WorkInBox が IMAP keyword を直接追加しても、Thunderbird で人間向けのタグとして正しく見えることが重要である。

---

## 9. テスト5: WorkInBox からタグを外せるか

### 手順

1. `wib-deadline` が付いた状態から開始する。
2. WorkInBox から `wib-deadline` を削除する。
3. Thunderbird を同期する。
4. Thunderbird 上で `締切あり` が外れたことを確認する。

これで双方向の基本テストが完了する。

```text
Thunderbird → IMAP → WorkInBox
WorkInBox   → IMAP → Thunderbird
```

---

## 10. テスト6: 別の Thunderbird でも同じタグになるか

固定 key を採用する大きな理由は、複数 PC で同じタグを扱えるようにすることである。

可能であれば2つ目の Thunderbird プロファイルまたは別 PC でも確認する。

### 手順

1. PC-A の Thunderbird にテスト用 MailExtension を入れる。
2. PC-B の Thunderbird にも同じ MailExtension を入れる。
3. 両方で `wib-deadline` → `締切あり` が登録されることを確認する。
4. PC-A でメールへ `締切あり` を付ける。
5. IMAP 同期する。
6. PC-B でも同じメールに `締切あり` が表示されることを確認する。
7. PC-B でタグを外す。
8. PC-A と WorkInBox の双方で `wib-deadline` が外れたことを確認する。

### 成功条件

各 PC が独自の key を作るのではなく、どの Thunderbird でも同じ `wib-deadline` を利用する。

---

## 11. 1タグの検証後に全タグへ展開する

`締切あり` のテストが成功したら、WorkInBox の全タグについて正式な key、表示名、色を決める。

現時点のタグは次の12種類である。

| 種別 | 表示名 | key |
| --- | --- | --- |
| 参照 | `重要` | 未決定 |
| 作業 | `締切あり` | `wib-deadline`（テスト候補） |
| 作業 | `スケジュール調整` | 未決定 |
| 作業 | `回答必要` | 未決定 |
| 作業 | `読む・検討` | 未決定 |
| 判定状態 | `判定保留` | 未決定 |
| 処理完了 | `締切登録済み` | 未決定 |
| 処理完了 | `スケジュール対応済み` | 未決定 |
| 待機 | `返信待ち` | 未決定 |
| 待機 | `対応待ち` | 未決定 |
| 履歴 | `依頼済み` | 未決定 |
| 終了 | `一括処理` | 未決定 |

最初から12個の key を仮決めして実装せず、**1個で仕組みを確認してから正式定義を決める**。

---

## 12. `重要` の既存タグについて

現在 Thunderbird で利用している `重要` タグの移行は、この基本テストとは分けて考える。

まず確認すべきことは、WorkInBox が決めた新しいタグ key を Thunderbird で問題なく利用できるかどうかである。

それが確認できた後で、既存 `重要` について次を決める。

- 現在の `重要` の IMAP keyword をそのまま利用するか。
- WorkInBox の正式 key を新しく決めるか。
- 新しい key にする場合、既存メールをどう一括移行するか。

したがって、`重要` の既存 keyword 調査を、今回のテストの前提条件にはしない。

---

## 13. キーボード操作の確認

全タグを正式登録する段階では、Thunderbird の数字キーによるタグ操作も確認する。

現時点の配置候補は次のとおり。

```text
1 = 重要
2 = 締切あり
3 = スケジュール調整
4 = 回答必要
5 = 読む・検討
6 = 判定保留
```

これはまだ最終仕様ではない。

まず `wib-deadline` の相互運用テストを成功させ、その後にタグ順序とキー操作を調整する。

---

## 14. WorkInBox 管理外タグを壊さないこと

WorkInBox は、自分が定義した `wib-*` key だけを操作する。

利用者が Thunderbird で独自に作成したタグや、標準 IMAP flag を変更してはいけない。

IMAP タグ書き込み実装では、FLAGS 全体を置換せず、対象の WorkInBox keyword だけを追加・削除する。

この点は v0.2 の実装テストでも必ず確認する。

---

## 15. このテストの完了条件

まず `締切あり` 1タグについて、以下がすべて成功すれば基本方式を採用できる。

- WorkInBox が決めた `wib-deadline` を Thunderbird のタグ key として登録できる。
- Thunderbird 上では `締切あり` と表示される。
- Thunderbird で付与すると IMAP に `wib-deadline` が保存される。
- Thunderbird で解除すると IMAP から `wib-deadline` が削除される。
- WorkInBox が `wib-deadline` を読み取れる。
- WorkInBox が `wib-deadline` を付けると Thunderbird に `締切あり` と表示される。
- WorkInBox が `wib-deadline` を外すと Thunderbird でもタグが外れる。
- 可能であれば別 PC / 別 Thunderbird プロファイルでも同じ key と表示名を利用できる。

ここまで確認できたら、**「WorkInBox がタグ定義の基準を持ち、Thunderbird はそのタグを表示・操作する」方式を採用する**。

その後に12タグの正式 key、色、数字キー配置を決め、v0.2 の IMAP タグ読み書き実装へ進む。
