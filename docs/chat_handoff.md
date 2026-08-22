# WorkInBox チャット引き継ぎ

この文書は、チャット上限・担当交代・環境切替などで WorkInBox の作業を別チャットへ引き継ぐための固定手順である。

現在の Issue 番号、commit SHA、残作業などの一時的な状態はこの文書には原則として書かない。
それらは `docs/current_work.md` を正本とする。

## 新しいチャットへの依頼文

> WorkInBox リポジトリの作業を引き継いでください。
>
> 最初に `docs/development_working_agreement.md` と `docs/current_work.md` を読み、
> GitHub / git の実状態と照合してください。
>
> `docs/current_work.md` と実状態が異なる場合は GitHub / git の実状態を優先し、
> `docs/current_work.md` を更新してから作業を再開してください。
>
> 仕様判断は `docs/design.md` を正本とし、必要な詳細設計と `docs/decision_log.md` を参照してください。
> `docs/roadmap.md` は中長期の実装順序であり、現在進捗の正本として扱わないでください。
>
> 中断理由が設計判断待ちでなければ、`docs/current_work.md` の「残作業」の先頭から再開してください。
>
> 実装途中で「これは設計上、新たに判断しないと危ない」という点が出た場合はそこで停止し、
> どの Issue / commit まで完了したか、Actions の状態、判断が必要な点を明確に報告してください。

## 引き継ぎ先が最初に読むもの

1. `docs/development_working_agreement.md`
2. `docs/current_work.md`
3. `docs/design.md`
4. 作業対象 Issue
5. 作業対象に対応する詳細設計
6. 必要に応じて `docs/decision_log.md`
7. `docs/roadmap.md`

## 実状態との照合

作業再開前に、可能な範囲で次を確認する。

- GitHub Issue の Open / Closed
- `git status -sb`
- `git log --oneline --decorate -n 10`
- `origin/main` とローカル `main` の差
- 未 push commit の有無
- 最新 GitHub Actions の結果

`docs/current_work.md` と異なる場合は、実状態を優先して修正する。

## 作業中断時

利用者から `作業中断` と指示された場合は、
`docs/development_working_agreement.md` の「作業中断」手順に従い、
`docs/current_work.md` を更新してから終了する。

特に次を残す。

- 最新の `作業再開` 以降に完了したこと
- commit SHA
- Actions の状態
- Issue の更新状態
- 現在の残作業
- 中断理由
- 設計判断待ちかどうか

## 文書の役割

- `docs/design.md`: 現行仕様の正本
- GitHub / git: 実装・Issue・Actions の実状態
- `docs/current_work.md`: 現在位置と残作業
- `docs/chat_handoff.md`: チャット引き継ぎ手順
- `docs/roadmap.md`: 中長期の実装順序・方向性
