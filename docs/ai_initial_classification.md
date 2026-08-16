# AI 初期分類

## 1. 目的

TrackingBox のスター付きメールのうち、専用ワークフロータグ、通常ワークフロータグ、`判定保留`、決定的な待機・専用ワークフロー状態タグが付いていないメールを、ローカル LLM で初期分類し、その結果を IMAP タグへ反映する。

AI は「このメールを追跡すべきか」を判定しない。対象メールには既に利用者の着眼判断としてスターが付いているためである。

初期分類では、専用ワークフローと通常ワークフローを独立して判定する。

## 2. AI 実行環境

v0.2 では Ollama を利用する。

既定値:

```yaml
ai:
  url: http://127.0.0.1:11434
  model: qwen2.5:7b
  body_max_chars: 4000
  timeout_seconds: 120
  keep_alive: 30m
  max_workers: 1
```

`body_max_chars` は引用除去等の前処理後の本文に適用する文字数上限である。

`keep_alive` は Ollama の `/api/generate` へそのまま渡し、分類処理の途中でモデルがアンロードされにくいようにする。

`max_workers` は WorkInBox 側で同時に処理するメール数である。安全側に 1〜4 の範囲に制限し、既定値を 1 とする。Ollama サーバー側で並列実行を明示的に有効化し、GPU/VRAM に余裕があることを確認した場合にだけ 2 以上を試す。

## 3. AI へ渡す情報

- 件名
- 差出人
- 宛先
- 利用者本人のメールアドレスと本人判定結果
- 引用等を機械的に除去した後の本文（最大 `ai.body_max_chars` 文字）

添付ファイル自体は初期分類では AI へ渡さない。

本文前処理は、現実的な best effort として次の順で行う。

```text
メール本文
  ↓
典型的な引用行・返信区切りを機械的に除去
  ↓
可能な範囲で今回新たに書かれた本文を残す
  ↓
署名区切り以降を可能な範囲で除去
  ↓
body_max_chars を適用
  ↓
AI 判定
```

現在の実装では、少なくとも `>` で始まる引用行、`On ... wrote:`、`-----Original Message-----`、標準的な `-- ` 署名区切りを対象とする。引用除去が完全であることは前提にしない。

本文欠損、添付依存、強い前後文脈依存などで通常ワークフローの判断材料そのものが不足している場合は、専用ワークフローが非該当なら `判定保留` の対象とする。

## 4. 分類原則

AI は次を同時に判定する。

### 専用ワークフロー

1. `締切あり` の必要性を独立判定する。
2. `スケジュール調整` の必要性を独立判定する。
3. 両方同時に該当してよい。
4. 専用ワークフローに該当しても、通常ワークフロー判定を省略しない。

`締切あり` と `スケジュール調整` は見逃しを減らすため再現率を重視する。

### 通常ワークフロー

通常ワークフローは次の4分類から1つを選ぶ。

- `返信必要`
- `見る・検討`
- `注目`
- `何もしなくてよい`

通常ワークフロータグ同士は排他的だが、専用ワークフロータグとは共存できる。

通常ワークフローの判断材料そのものが不足している場合だけ `pending` とする。通常の曖昧さでは `pending` にしない。

`判定保留` は **AI 判定済み・専用ワークフロー非該当・通常ワークフローだけ未確定** を表す。そのため専用ワークフローに該当したメールへ `判定保留` は付けない。

### `何もしなくてよい`

専用ワークフローも非該当で、通常ワークフローが `何もしなくてよい` の場合は、AI 初期分類の完了結果として次の状態へ進める。

```text
一括処理 + ☆
```

つまり `wib-bulk` を付け、スターを外す。SQLite の tracking status も inactive/unstarred へ更新する。

専用ワークフローが存在する場合に通常ワークフローが `何もしなくてよい` でも、専用ワークフローを進める必要があるためスターは外さない。

## 5. JSON 出力

Ollama の Structured Outputs を利用し、次の形の JSON を要求する。

```json
{
  "deadline": true,
  "schedule": false,
  "normal_workflow": "answer",
  "reason": "提出期限があり返信も必要なため"
}
```

`normal_workflow` は次のいずれかとする。

```text
answer   -> 返信必要
review   -> 見る・検討
watch    -> 注目
none     -> 何もしなくてよい
pending  -> 判断材料不足
```

Python 側でも値を検証し、許可されたタグ状態へ正規化する。

例:

```text
deadline=true + normal_workflow=answer
  -> wib-deadline + wib-answer

schedule=true + normal_workflow=watch
  -> wib-schedule + wib-watch

deadline=false + schedule=false + normal_workflow=review
  -> wib-review

deadline=false + schedule=false + normal_workflow=pending
  -> wib-pending

deadline=false + schedule=false + normal_workflow=none
  -> wib-bulk + スター解除
```

専用ワークフローが true で `normal_workflow=pending` の場合は、専用ワークフロータグだけを採用し `wib-pending` は付けない。

## 6. 実行タイミング

通常同期の完了後に自動実行する。

処理順序:

```text
TriageBox
  -> IMAP / SQLite 通常同期
  -> active メールを列挙
  -> IMAP FLAGS を確認
  -> 既に初期分類または決定的状態があればスキップ
  -> 未分類メールだけ Ollama へ送信
  -> JSON を検証・正規化
  -> IMAP タグ / スターへ反映
```

初期分類済み・処理済み判定に含めるタグ:

- `wib-deadline`
- `wib-schedule`
- `wib-answer`
- `wib-review`
- `wib-watch`
- `wib-pending`
- `wib-bulk`

決定的状態として通常の AI 判定から除外するタグには、少なくとも次を含める。

- `wib-waiting-reply`
- `wib-waiting-action`
- `wib-action-ready`

全件再確認では AI 初期分類を自動実行しない。

Web UI からの通常同期と全件再確認は同時実行しない。同じ Web プロセスで同期処理が進行中に別の同期要求が来た場合は、2本目を開始せず「同期処理は既に実行中」と表示する。

## 7. 並列化と性能計測

未分類メールの抽出は先に行い、その後の AI 推論と結果タグ付与を `ai.max_workers` 件まで並列化できる。

各メールについて、AI分類開始から IMAP 状態反映完了までの時間をログへ記録する。

成功例:

```text
AI classified <message-id> in 8.42s -> wib-deadline,wib-answer
AI classified <message-id> in 3.10s -> wib-bulk + unstarred
```

全体についても件数と総時間をログへ記録する。

```text
AI classification starting: 12 messages, 1 worker(s)
AI classification finished: 12/12 messages in 102.31s
```

並列数を増やせば必ず高速になるとは限らない。特に Ollama 側の同時推論数が 1 の状態で WorkInBox だけを 2 以上にすると、待ち行列によって1件あたりの待機時間が増え、WorkInBox の API タイムアウトに到達しやすくなる。そのため既定値は `max_workers: 1` とする。

## 8. 判定保留の確定フロー

`判定保留` は AI の技術的エラーを表すタグではない。Ollama のタイムアウトや通信失敗時は未分類のまま残し、次回の通常同期で再試行する。

`判定保留` になるのは次の条件である。

```text
AI 初期判定は実行済み
AND 締切あり = false
AND スケジュール調整 = false
AND 通常ワークフローの判断材料不足
```

したがって `/pending` 画面で利用者が確定するのは通常ワークフローだけとし、次の4択に限定する。

```text
返信必要
見る・検討
注目
何もしなくてよい
```

`締切あり` / `スケジュール調整` / `締切あり + スケジュール調整` は判定保留の確定選択肢に含めない。

確定時の状態遷移は次のとおり。

```text
判定保留 + ★
  -> 返信必要 + ★
  -> 見る・検討 + ★
  -> 注目 + ★
  -> 一括処理 + ☆   （何もしなくてよい）
```

通常ワークフローを確定した場合は `wib-pending` と、残っている矛盾する通常ワークフロー系 keyword / `wib-bulk` を除去する。専用ワークフロー keyword はこの操作では変更しない。

`何もしなくてよい` では `wib-bulk` を付けてスターを外し、SQLite の tracking status も inactive/unstarred に更新する。スター解除に失敗した場合は、可能な範囲で `wib-bulk` を外して `wib-pending` を戻し、再実行可能な状態へロールバックする。

## 9. IMAP 書き込み

分類結果は SQLite へタグ状態として複製せず、IMAP keyword を正本とする。

`締切あり + スケジュール調整 + 返信必要` のような複数タグ分類は、1 回の `UID STORE +FLAGS.SILENT` でまとめて付与する。

`何もしなくてよい` では `wib-bulk` を付与した後にスターを外す。スター解除に失敗した場合は、可能な範囲で `wib-bulk` をロールバックし、未分類として再試行可能な状態を保つ。

既存の Thunderbird 標準 flag や WorkInBox 管理外 keyword は変更しない。

## 10. エラー処理

Ollama が停止している、タイムアウトする、JSON が不正などの AI エラーは、IMAP 同期そのものの失敗とは分離する。

- メールの tracking status は変更しない。
- 対象メールには分類タグを付けない。
- 他メールの分類は継続する。
- Web UI と CLI に AI 分類エラーを表示する。
- 次回の通常同期で、まだ未分類なら再試行する。

IMAP FLAGS の事前確認に失敗した場合も AI 分類エラーとして扱い、他メールの処理は継続する。

## 11. プロンプト管理

実際の system prompt、JSON Schema、本文前処理は `src/workinbox/ai_classifier.py` に置く。

プロンプトや前処理を変更する場合は、この文書および `docs/design.md` の TrackingBox 原則と矛盾しないことを確認する。
