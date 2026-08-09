# AI 初期分類

## 1. 目的

TrackingBox の active メールのうち、作業タグも `判定保留` も付いていないメールを、ローカル LLM で初期分類し、その結果を IMAP タグへ自動反映する。

AI は「このメールを追跡すべきか」を判定しない。対象メールには既に利用者がスターを付けており、何らかの確認・対応が必要という利用者判断が済んでいるためである。

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

本文長は設定値とする。既定では本文の先頭 4,000 文字だけを分類入力へ渡す。

`keep_alive` は Ollama の `/api/generate` へそのまま渡し、分類処理の途中でモデルがアンロードされにくいようにする。

`max_workers` は WorkInBox 側で同時に処理するメール数である。v0.2 では安全側に 1〜4 の範囲に制限し、既定値を 1 とする。Ollama サーバー側で並列実行を明示的に有効化し、GPU/VRAM に余裕があることを確認した場合にだけ 2 以上を試す。

## 3. AI へ渡す情報

- 件名
- 差出人
- 宛先
- 本文の先頭 `ai.body_max_chars` 文字

添付ファイル自体は v0.2 の初期分類では AI へ渡さない。

本文欠損、添付依存、強い前後文脈依存などで分類材料そのものが不足している場合は `判定保留` の対象とする。

本文長を短くすると、入力トークン数が減るため推論時間の短縮が期待できる。一方で、締切や依頼内容が本文後半にあるメールを見落とす可能性が上がるため、速度だけでなく分類精度も実メールで確認して調整する。

## 4. 分類順序

AI には次の優先順を明示する。

1. `締切あり` を判定する。
2. `スケジュール調整` を独立して判定する。
3. 1 または 2 が該当すれば、そのタグだけを採用する。両方同時付与してよい。
4. 1 と 2 がともに非該当なら `回答必要` を判定する。
5. それにも該当しなければ `読む・検討` とする。
6. 分類材料そのものが不足している場合だけ `判定保留` とする。

`締切あり`、`スケジュール調整`、`回答必要` は見逃しを減らすため再現率を重視する。

## 5. JSON 出力

Ollama の Structured Outputs を利用し、次の形の JSON を要求する。

```json
{
  "deadline": true,
  "schedule": false,
  "answer_required": false,
  "review": false,
  "pending": false,
  "reason": "提出期限が明示されているため"
}
```

Python 側でも型を確認し、最終的に許可されたタグ組み合わせへ正規化する。

優先順位:

```text
deadline / schedule
  -> wib-deadline / wib-schedule

answer_required
  -> wib-answer

review
  -> wib-review

pending
  -> wib-pending

すべて false
  -> wib-review
```

LLM が矛盾した boolean を返しても、IMAP へ任意の組み合わせをそのまま書き込まない。

## 6. 実行タイミング

通常同期の完了後に自動実行する。

処理順序:

```text
IMAP / SQLite 通常同期
  -> active メールを列挙
  -> IMAP FLAGS を確認
  -> 既に初期分類タグがあればスキップ
  -> 未分類メールだけ Ollama へ送信
  -> JSON を検証・正規化
  -> IMAP タグへ反映
```

初期分類済みとみなすタグ:

- `wib-deadline`
- `wib-schedule`
- `wib-answer`
- `wib-review`
- `wib-pending`

`重要` など、初期作業分類とは独立したタグだけが付いているメールは分類対象のままとする。

全件再確認では AI 初期分類を自動実行しない。

Web UI からの通常同期と全件再確認は同時実行しない。同じ Web プロセスで同期処理が進行中に別の同期要求が来た場合は、2本目を開始せず「同期処理は既に実行中」と表示する。これにより二重クリックなどで同じ未分類メールが同時に Ollama へ送られることを防ぐ。

## 7. 並列化と性能計測

未分類メールの抽出は先に行い、その後の AI 推論と結果タグ付与を `ai.max_workers` 件まで並列化できる。

各メールについて、AI分類開始から IMAP タグ付与完了までの時間をログへ記録する。

成功例:

```text
AI classified <message-id> in 8.42s -> wib-deadline
```

全体についても件数と総時間をログへ記録する。

```text
AI classification starting: 12 messages, 1 worker(s)
AI classification finished: 12/12 messages in 102.31s
```

このログにより、本文長や並列数を変更したときの効果を実測できるようにする。

並列数を増やせば必ず高速になるとは限らない。特に Ollama 側の同時推論数が 1 の状態で WorkInBox だけを 2 以上にすると、待ち行列によって1件あたりの待機時間が増え、WorkInBox の API タイムアウトに到達しやすくなる。そのため既定値は `max_workers: 1` とする。

## 8. IMAP 書き込み

分類結果は SQLite へタグ状態として保存せず、IMAP を正本とする。

`締切あり + スケジュール調整` のような複数タグ分類は、1 回の `UID STORE +FLAGS.SILENT` でまとめて付与する。

これにより、1 個目のタグだけ付いて 2 個目の付与に失敗した結果、そのメールが分類済み扱いになることを避ける。

既存の Thunderbird 標準 flag や WorkInBox 管理外 keyword は変更しない。

## 9. エラー処理

Ollama が停止している、タイムアウトする、JSON が不正などの AI エラーは、IMAP 同期そのものの失敗とは分離する。

- メールの tracking status は変更しない。
- 対象メールには分類タグを付けない。
- 他メールの分類は継続する。
- Web UI と CLI に AI 分類エラーを表示する。
- 次回の通常同期で、まだ未分類なら再試行する。

IMAP FLAGS の事前確認に失敗した場合も AI 分類エラーとして扱い、他メールの処理は継続する。

## 10. プロンプト管理

実際の system prompt と JSON Schema は `src/workinbox/ai_classifier.py` に置く。

プロンプトを変更する場合は、この文書の分類原則と矛盾しないことを確認する。
