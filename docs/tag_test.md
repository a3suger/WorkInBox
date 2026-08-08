# Thunderbird タグ / IMAP keyword 確認手順

## 1. 目的

WorkInBox が Thunderbird のタグを IMAP 上で正しく読み書きできるようにする前に、
Thunderbird で表示されるタグ名と、IMAP サーバー上の `FLAGS` / keyword の対応を確認する。

この確認結果を、WorkInBox の作業タグ読み書き実装の根拠として使う。

確認対象の例:

- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`
- `判定保留`

このテストでは WorkInBox からタグを書き込まない。
診断コマンドは IMAP mailbox を `readonly=True` で開き、指定 UID に対して `UID FETCH (UID FLAGS)` を行うだけである。

---

## 2. 事前準備

### 2.1 最新コードを取得する

```bash
git pull
```

### 2.2 venv を有効にする

macOS / Linux の例:

```bash
source .venv/bin/activate
```

### 2.3 editable install を更新する

新しい診断コマンドを使えるようにする。

```bash
python -m pip install -e .
```

### 2.4 WorkInBox の通常同期を一度実行する

テスト対象メールの UID が SQLite に保存されている状態にする。

```bash
python -m workinbox.main --config config.yaml
```

---

## 3. テスト対象メールを決める

本番業務メールではなく、可能なら自分宛てに送ったテストメールを1通使う。

Thunderbird 上でそのメールを INBOX に置き、スターを付けて WorkInBox の同期対象にする。

通常同期後、SQLite の `emails` テーブルから対象メールの UID を確認する。

例:

```sql
SELECT
    uid,
    message_id,
    subject,
    tracking_status
FROM emails
ORDER BY id DESC;
```

対象メールの `uid` を控える。

例:

```text
uid = 12345
```

UID は mailbox と UIDVALIDITY の組み合わせで意味を持つ。
診断コマンドは `config.yaml` の `imap.mailbox` を対象にするため、テスト中に対象メールを別フォルダーへ移動しないこと。

---

## 4. タグを付ける前の FLAGS を記録する

Thunderbird で対象メールにテスト対象のタグが付いていないことを確認する。

次を実行する。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

または:

```bash
python -m workinbox.imap_debug --config config.yaml --uid 12345
```

出力例:

```text
Mailbox: INBOX
UIDVALIDITY: 987654
UID: 12345
FLAGS:
  \\Seen
  \\Flagged
```

この結果を「タグ付与前」として記録する。

---

## 5. Thunderbird でタグを付ける

Thunderbird で対象メールに確認したいタグを1個だけ付ける。

最初は、既存タグとの区別がしやすいように、例えば次のような専用タグを作って試してもよい。

```text
WIBテスト
```

タグを付けた後、Thunderbird が IMAP サーバーへ変更を反映するまで少し待つ。

---

## 6. タグを付けた後の FLAGS を確認する

同じ UID で再度実行する。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

例:

```text
Mailbox: INBOX
UIDVALIDITY: 987654
UID: 12345
FLAGS:
  \\Seen
  \\Flagged
  $label1
```

またはサーバー / Thunderbird の設定によっては、別の keyword が見える可能性がある。

重要なのは、タグ付与前とタグ付与後で **新しく増えた FLAGS / keyword** を確認することである。

例:

```text
Thunderbird 表示名: WIBテスト
付与前: \\Seen \\Flagged
付与後: \\Seen \\Flagged $label1
追加された keyword: $label1
```

この場合は、Thunderbird 上の `WIBテスト` と IMAP keyword `$label1` が対応している可能性が高い。

1回の結果だけで決め打ちせず、タグを外して同じ keyword が消えることも確認する。

---

## 7. タグを外した後も確認する

Thunderbird で同じタグを外し、もう一度診断コマンドを実行する。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

タグ付与時に増えた keyword が消えれば、対応関係をより確実に確認できる。

確認は次の3状態で行う。

1. タグなし
2. タグあり
3. タグを再度外した状態

---

## 8. WorkInBox の各タグについて記録する

本実装前に、少なくとも次の対応を確認する。

| Thunderbird 表示名 | IMAP keyword | 付与確認 | 削除確認 | 備考 |
| --- | --- | --- | --- | --- |
| 締切あり | 未確認 |  |  |  |
| スケジュール調整 | 未確認 |  |  |  |
| 回答必要 | 未確認 |  |  |  |
| 読む・検討 | 未確認 |  |  |  |
| 判定保留 | 未確認 |  |  |  |

Thunderbird のタグ設定や IMAP サーバーの挙動によって keyword の表現が異なる可能性があるため、実測結果を優先する。

---

## 9. 複数タグの確認

単独タグの対応が確認できた後、必要に応じて複数タグを同時に付ける。

特に WorkInBox では将来、次の組み合わせを扱う。

```text
締切あり + スケジュール調整
```

この2つを Thunderbird 上で同時に付け、両方の keyword が FLAGS に同時に存在できることを確認する。

`回答必要` や `読む・検討` の排他制御は WorkInBox 側の業務ルールであり、この診断では IMAP が複数 keyword を保持できるかを観察するだけとする。

---

## 10. 注意事項

- 診断コマンドは読み取り専用であり、WorkInBox から FLAGS を変更しない。
- テスト中は対象メールを別 mailbox へ移動しない。
- UIDVALIDITY が変わった場合、以前控えた UID をそのまま信用しない。
- `\\Seen`、`\\Flagged` などの標準 IMAP flag と、タグ用途の keyword を区別して記録する。
- Thunderbird の表示名と IMAP keyword が同じ文字列とは限らないため、実測前にマッピングを決めない。
- このテストが終わるまでは、WorkInBox から本番メールへタグを書き込む実装を有効にしない。

---

## 11. テスト完了条件

ステップ6の IMAP 作業タグ読み書き実装へ進む前に、次を確認する。

- Thunderbird でタグを付けると対応する IMAP keyword が増える
- Thunderbird でタグを外すと対応する IMAP keyword が消える
- WorkInBox が `UID FETCH (UID FLAGS)` でその変化を読み取れる
- WorkInBox で使用する各タグの表示名と IMAP keyword の対応が記録できている
- `締切あり` と `スケジュール調整` を同時に保持できることを必要に応じて確認できている

この結果をもとに、ステップ6では IMAP keyword の読み取り・付与・削除と Thunderbird 表示名のマッピングを実装する。
