# WorkInBox 開発ロードマップ

## 方針

WorkInBox は Thunderbird を置き換えるメールクライアントではなく、メールから発生する仕事を整理するための業務支援システムである。

メール本文はメールサーバを正本、WorkInBox の内部状態と正式締切は SQLite を正本、作業タグは IMAP keyword を正本とする。

締切は SQLite に正式登録し、Thunderbird には SQLite から生成した読み取り専用 `.ics` / VTODO を購読させる。

CalDAV と双方向編集は v0.2 の対象外とする。

---

## v0.1 — メール追跡基盤【完了】

- IMAP 接続
- スター付きメール探索
- SQLite へのメール情報保存
- 管理対象メールの継続追跡
- スター解除・移動検出

---

## v0.2 — TrackingBox MVP +