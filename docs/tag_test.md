# Thunderbird タグ / IMAP keyword 確認手順

## 1. 目的

WorkInBox が Thunderbird のタグを IMAP 上で正しく読み書きできるようにする前に、
Thunderbird で表示されるタグ名と、IMAP サーバー上の `FLAGS` / keyword の対応を確認する。

この確認結果を、WorkInBox のタグ読み書き実装の根拠として使う。

今回確認する WorkInBox のタグは、設計書に定義されている以下の **11 種類すべて** とする。

### 作業タグ

- `締切あり`
- `スケジュール調整`
- `回答必要`
- `読む・検討`

### 判定状態タグ

- `判定保留`

### 処理完了タグ

- `締切登録済み`
- `スケジュール対応済み`

### 待機タグ

- `返信待ち`
- `対応待ち`

### 履歴タグ

- `依頼済み`

### 終了タグ

- `一括処理`

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

診断コマンドを使えるようにする。

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

同じメールを繰り返し使ってよいが、**各タグのテスト開始前には WorkInBox 用タグをすべて外した基準状態へ戻す**。
これにより、どの keyword がどの Thunderbird タグに対応したかを判別しやすくする。

---

## 4. 基準となる FLAGS を記録する

Thunderbird で対象メールから WorkInBox 用タグをすべて外した状態にする。

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

この結果を「基準 FLAGS」として記録する。

`\\Seen` や `\\Flagged` などの標準 IMAP flag は WorkInBox のタグではないので、タグ用 keyword と区別する。

---

## 5. 11種類のタグを1つずつテストする

以下の **11種類すべて** について、同じ手順を繰り返す。

1. 対象メールから WorkInBox 用タグをすべて外す。
2. 診断コマンドを実行し、基準 FLAGS と同じ状態であることを確認する。
3. Thunderbird で確認対象のタグを **1つだけ** 付ける。
4. Thunderbird が IMAP サーバーへ変更を反映するまで少し待つ。
5. 診断コマンドを再実行する。
6. 基準 FLAGS と比較して、新しく増えた keyword を記録する。
7. Thunderbird でそのタグを外す。
8. 診断コマンドを再実行する。
9. 追加された keyword が消えたことを確認する。
10. 次のタグへ進む。

対象タグ:

1. `締切あり`
2. `スケジュール調整`
3. `回答必要`
4. `読む・検討`
5. `判定保留`
6. `締切登録済み`
7. `スケジュール対応済み`
8. `返信待ち`
9. `対応待ち`
10. `依頼済み`
11. `一括処理`

---

## 6. タグを付けた後の FLAGS の見方

同じ UID で診断コマンドを実行する。

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

サーバー / Thunderbird の設定によっては、`$label1` 以外の keyword が見える可能性がある。

重要なのは、タグ付与前とタグ付与後で **新しく増えた FLAGS / keyword** を確認することである。

例:

```text
Thunderbird 表示名: 締切あり
付与前: \\Seen \\Flagged
付与後: \\Seen \\Flagged $label1
追加された keyword: $label1
```

1回の結果だけで決め打ちせず、タグを外して同じ keyword が消えることまで確認する。

---

## 7. 全タグの記録表

ステップ6の本実装前に、以下の **11種類すべて** を埋める。

| 種別 | Thunderbird 表示名 | IMAP keyword | 付与確認 | 削除確認 | 備考 |
| --- | --- | --- | --- | --- | --- |
| 作業 | 締切あり | 未確認 |  |  |  |
| 作業 | スケジュール調整 | 未確認 |  |  |  |
| 作業 | 回答必要 | 未確認 |  |  |  |
| 作業 | 読む・検討 | 未確認 |  |  |  |
| 判定状態 | 判定保留 | 未確認 |  |  |  |
| 処理完了 | 締切登録済み | 未確認 |  |  |  |
| 処理完了 | スケジュール対応済み | 未確認 |  |  |  |
| 待機 | 返信待ち | 未確認 |  |  |  |
| 待機 | 対応待ち | 未確認 |  |  |  |
| 履歴 | 依頼済み | 未確認 |  |  |  |
| 終了 | 一括処理 | 未確認 |  |  |  |

Thunderbird のタグ設定や IMAP サーバーの挙動によって keyword の表現が異なる可能性があるため、実測結果を優先する。

---

## 8. 複数タグの組み合わせを確認する

単独11タグの対応がすべて確認できた後、WorkInBox の実際の運用で同時保持する組み合わせを確認する。

### 8.1 締切 + スケジュール

```text
締切あり + スケジュール調整
```

両方の keyword が同時に FLAGS に存在できることを確認する。

### 8.2 作業タグ + 処理完了タグ

次も確認する。

```text
締切あり + 締切登録済み
```

```text
スケジュール調整 + スケジュール対応済み
```

処理完了タグは対応する作業タグを消す代わりではないため、両方が同時に保持できることを確認する。

### 8.3 支援者依頼の履歴 / 待機

必要に応じて次の組み合わせも確認する。

```text
依頼済み + 対応待ち
```

`依頼済み` は履歴、`対応待ち` は現在の待機状態なので、別 keyword として同時保持できることを確認する。

### 8.4 排他ルールについて

`回答必要` と `読む・検討` などの排他制御は WorkInBox 側の業務ルールである。

この診断の目的は Thunderbird / IMAP が各 keyword を正しく保持できるかの確認なので、禁止組み合わせを積極的に作る必要はない。

---

## 9. テスト結果の判断

各タグについて、次の3状態を確認する。

1. **タグなし**: 対応 keyword が存在しない。
2. **タグあり**: 対応 keyword が1つ増える。
3. **タグ削除後**: 対応 keyword が再び消える。

3状態が確認できた場合、その Thunderbird 表示名と IMAP keyword の対応を確定候補として記録する。

異なるタグで同じ keyword が現れた場合や、タグを外しても keyword が残る場合は、その時点でステップ6の書き込み実装へ進まず、原因を確認する。

---

## 10. 注意事項

- 診断コマンドは読み取り専用であり、WorkInBox から FLAGS を変更しない。
- テスト中は対象メールを別 mailbox へ移動しない。
- UIDVALIDITY が変わった場合、以前控えた UID をそのまま信用しない。
- `\\Seen`、`\\Flagged` などの標準 IMAP flag と、タグ用途の keyword を区別して記録する。
- Thunderbird の表示名と IMAP keyword が同じ文字列とは限らないため、実測前にマッピングを決めない。
- 11タグは省略せず、すべて単独で付与・削除を確認する。
- 複数タグテストは、単独11タグの確認が終わってから行う。
- このテストが終わるまでは、WorkInBox から本番メールへタグを書き込む実装を有効にしない。

---

## 11. テスト完了条件

ステップ6の IMAP タグ読み書き実装へ進む前に、次をすべて確認する。

- 11種類すべてについて Thunderbird 表示名と IMAP keyword の対応が記録できている。
- 11種類すべてについて Thunderbird でタグを付けると対応 keyword が増える。
- 11種類すべてについて Thunderbird でタグを外すと対応 keyword が消える。
- WorkInBox が `UID FETCH (UID FLAGS)` で11種類すべての変化を読み取れる。
- `締切あり` + `スケジュール調整` を同時保持できる。
- `締切あり` + `締切登録済み` を同時保持できる。
- `スケジュール調整` + `スケジュール対応済み` を同時保持できる。
- 必要に応じて `依頼済み` + `対応待ち` を同時保持できる。
- 異なるタグが意図せず同じ keyword に割り当てられていないことを確認できている。

この結果をもとに、ステップ6では IMAP keyword の読み取り・付与・削除と Thunderbird 表示名のマッピングを実装する。
