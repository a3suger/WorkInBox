# スケジュール支援と返信時の着眼点遷移

更新日: 2026-08-17

この文書は、2026-08-12 の実機 E2E テストを起点に整理したスケジュール調整支援の詳細設計である。

現行仕様の正本は `docs/design.md` とし、この文書は実装上の流れを補足する。過去の E2E 時点から変更された責務については、現在の正本に合わせて更新している。

---

## 1. 基本原則

スケジュール調整は専用ワークフローであり、起点メール M1 と、支援者へ依頼する別スレッド M2/M3 を区別する。

- M1 = スケジュール調整専用ワークフローの起点メール
- M2 = WIB を起点として支援者へ作成した新規依頼メール
- M3 = M2 に対する支援者返信
- M4 = M1 の標準メールスレッド上の継続メール

M2/M3 は M1 の標準メールスレッドとは別スレッドであり、支援者とのやり取りだけを理由に `current_focus_message_id` を移動しない。

---

## 2. 支援者への依頼作成

M1 から支援者へ依頼するとき、Thunderbird Extension は M1 への Reply ではなく、M1 を本文内転送した別スレッドのメール M2 を作成する。これにより、支援者は元メールの内容を確認できる一方、M1 の標準返信スレッドには M2 を参加させない。

M2 には次のヘッダを付ける。

```text
X-WorkInBox-Origin-Message-ID: <M1 Message-ID>
```

利用者が Thunderbird で M2 を送信し、新規メール作成が成立した時点で Thunderbird Extension が M1 に履歴タグ `依頼済み` を付ける。

```text
M1: スケジュール調整 + ★
↓ M2 送信成立
M1: スケジュール調整 + 依頼済み + ★
```

`依頼済み` は完了タグではなく、専用ワークフローから支援者へ依頼した履歴である。通常は解除しない。

---

## 3. self-Cc の M2 を TriageBox が確認したとき

M2 は自分を Cc に入れて送信し、そのコピーを INBOX で TriageBox が確認する。

TriageBox の責務は次の二つである。

1. M2 に `対応待ち + ★` を付ける。
2. M1/M2 relation を SQLite に保存する。

TriageBox は M1 の `依頼済み` を付け直さない。

```text
M2 新規メール作成成立
→ Thunderbird Extension: M1 に 依頼済み

self-Cc M2 を TriageBox が確認
→ M2 に 対応待ち + ★
→ M1/M2 relation を SQLite に保存
```

この責務分離により、`依頼済み` は送信成立の履歴、`対応待ち` と relation は INBOX で M2 を確認した事実として扱う。

---

## 4. 支援者返信 M3

支援者が M2 に返信した M3 は、標準 `In-Reply-To` / `References` から M2 を特定し、SQLite relation から M1 の専用ワークフローに到達する。

M3 自体に `X-WorkInBox-Origin-Message-ID` は不要である。

TriageBox が M3 を支援者返信と決定できた場合、状態は次のように遷移する。

```text
M2: 対応待ち + ★
↓ M3 到着
M2: 対応待ち + 一括処理 + ☆
M3: 対応あり + ★
```

- M2 の `対応待ち` は依頼履歴として残す。
- M2 に `一括処理` を付け、スターを外す。
- M3 に `対応あり` とスターを付ける。
- M3 に `スケジュール調整` は付けない。
- M3 は通常 AI 再分類へ送らない。
- M1 は未完了の `スケジュール調整` として維持する。

---

## 5. 起点メール M1 の完了

支援者から M3 が届いただけではスケジュール調整専用ワークフローは完了しない。

利用者が WIB で支援内容を確認し、本来必要なスケジュール対応が完了した時点で `スケジュール対応済み` とする。

起点メール M1 は専用ワークフローが完了するまで起点として維持する。

専用ワークフロー完了後の通常ワークフローへの接続は `docs/design.md` の専用ワークフロー終了規則に従う。

---

## 6. current focus との関係

`workflow_origin_message_id` と `current_focus_message_id` は次の意味を持つ。

```text
workflow_origin_message_id = 専用ワークフローの起点メール
current_focus_message_id   = M1 の標準メールスレッド上で現在着眼しているメール
```

M2/M3 は支援者との別スレッドなので `current_focus_message_id` を変更しない。

M1 の標準メールスレッド上に M4 が届き、relation からその継続が確定した場合は M4 が新しい current focus になり得る。

永続化の具体的実装は Issue #12 で扱う。

---

## 7. 実装上の責務

```text
Thunderbird Extension
- WIB から M2 を新規 compose
- X-WorkInBox-Origin-Message-ID を付与
- 送信成立時に M1 へ 依頼済み

TriageBox
- self-Cc M2 を確認
- M2 へ 対応待ち + ★
- M1/M2 relation 保存
- M3 を In-Reply-To / References + relation で検出
- M2 を 対応待ち + 一括処理 + ☆
- M3 を 対応あり + ★

WIB Web
- 専用ワークフローの閲覧・進行・完了操作
```

この文書の詳細が `docs/design.md` と矛盾する場合は `docs/design.md` を優先する。
