# Extension締切サマリーと限定CalDAV仕様

関連Issue: [#32 Extension締切サマリーと限定CalDAV双方向編集を追加する](https://github.com/a3suger/WorkInBox/issues/32)

## 1. 位置付け

この文書は、ThunderbirdのToDo画面からWorkInBox（WIB）の正式締切を編集するための限定CalDAVと、Extensionダッシュボードの締切サマリーを定義する詳細仕様である。

現行実装はSQLiteから生成した読み取り専用`deadlines.ics`をThunderbirdで購読する方式である。#32が完了するまでは現行方式を使用し、この文書は実装予定の確定仕様として扱う。

2026-09-01時点で、第1段階の締切サマリーAPI、Extension件数表示、Thunderbird ToDo画面へのボタンは実装済みである。完了状態をSQLiteへ追加するまでは、現行の正式締切をすべて未完了として集計する。限定CalDAV導入後は同じAPIから完了済みを除外する。

## 2. 目的

- Extensionダッシュボードで、期限超過と今後7日以内の正式締切を把握できるようにする。
- 件数からThunderbird標準のToDo画面へ進めるようにする。
- ThunderbirdのToDo詳細で行った変更をWIBへ反映する。
- WIBとThunderbirdのどちらから変更しても、SQLiteを正式締切の正本として一貫させる。
- VTODOの`mid:`リンクから元メールへ戻る既存の速い導線を維持する。

## 3. 正本と責務

- 正式締切の正本は引き続きWIBのSQLiteとする。
- CalDAV resourceはSQLiteの1件の締切を表す読み書き可能な表現とする。
- Thunderbirdは標準ToDo UIとCalDAV clientを担当する。
- ExtensionはWIBの締切サマリーを表示し、ThunderbirdのToDo画面を開く導線を担当する。
- メール本文とIMAP状態はCalDAVへ複製しない。

## 4. Extensionダッシュボード

WIB接続中に次の2件数を表示する。

| 表示 | 条件 |
| --- | --- |
| 期限超過 | 未完了かつ、現在より前が期限 |
| 今後7日以内 | 未完了かつ、期限超過ではなく、現在から7日後までが期限 |

- 件数はIMAPタグではなくSQLiteの正式締切から取得する。
- 完了済み締切は両方から除外する。
- 日付だけの期限はWIBの設定タイムゾーンにおける日付として比較する。
- 日時付き期限は絶対時刻へ正規化して比較する。
- 2区分は重複させない。
- WIB接続不可時は直近取得値と取得日時を表示してよいが、現在値と区別する。
- ボタンからThunderbird標準のToDo画面を開く。初回実装では期限区分に対応したThunderbird内フィルターまでは必須としない。

## 5. SQLiteとVTODOの対応

現在の`deadlines`に状態・着手日時・重要度を追加する。

| SQLite | iCalendar / VTODO | Thunderbird | WIB Web |
| --- | --- | --- | --- |
| `id` | `X-WORKINBOX-DEADLINE-ID` | 内部識別 | 非表示 |
| `source_message_id` | `X-WORKINBOX-MESSAGE-ID`、`URL:mid:` | 元メール導線 | 元メール導線 |
| `title` | `SUMMARY` | 表示・編集 | 表示・編集 |
| `start_at`（追加、nullable） | `DTSTART` | 表示・編集 | **非表示・編集不可** |
| `due_at` + `timezone` | `DUE` | 表示・編集 | 表示・編集 |
| `description` | `DESCRIPTION` | 表示・編集 | 表示・編集 |
| `status`（追加） | `STATUS` | 表示・編集 | 初回は非表示・編集不可 |
| `completed_at`（追加、nullable） | `COMPLETED` | 完了操作と同期 | 初回は非表示・編集不可 |
| `percent_complete`（追加） | `PERCENT-COMPLETE` | 完了操作と同期 | 初回は非表示・編集不可 |
| `priority`（追加） | `PRIORITY` | 表示・編集 | 初回は非表示・編集不可 |
| `created_at` | `CREATED` | 派生表示 | 非表示 |
| `updated_at` | `LAST-MODIFIED`、ETag生成元 | 競合検知 | 非表示 |
| `created_by` | `X-WORKINBOX-CREATED-BY` | 参照のみ | 非表示 |

### 着手日時

`start_at`はThunderbirdのToDoで入力・修正するために保持する。WIB Webでは着手日時を表示せず、入力欄も設けない。

WIB Webから`title`、`due_at`、`description`を更新するときは、既存の`start_at`を読み出してそのまま保持する。Web更新によってCalDAV専用項目を`NULL`や初期値へ戻してはならない。

### 完了状態

初回実装では未完了と完了の2状態を扱う。

```text
未完了: STATUS=NEEDS-ACTION, PERCENT-COMPLETE=0, COMPLETEDなし
完了:   STATUS=COMPLETED, PERCENT-COMPLETE=100, COMPLETEDあり
```

Thunderbirdで完了を取り消した場合は未完了へ戻し、`completed_at`を空にする。任意の進捗率は初回対象外とする。

### 重要度

`PRIORITY`はiCalendarの値を保存する。初回UIではThunderbird標準の段階を使用し、少なくとも`0`（未指定）、`1`（高）、`5`（通常）、`9`（低）を往復できるようにする。

### DESCRIPTIONと元メール

限定CalDAV移行後の`DESCRIPTION`はSQLiteの`description`だけを表す。現行の読み取り専用VTODOで自動追加している「締切の確認・修正」WIB URLは含めない。Thunderbirdで編集したメモとWIBのメモを損失なく往復させるためである。

元メール導線は次を維持する。

```text
URL:mid:{Message-ID}
X-WORKINBOX-MESSAGE-ID:{Message-ID}
```

## 6. 不変項目と入力検証

- `UID`は`workinbox-deadline-{id}@workinbox.local`から変更しない。
- `UID`、締切ID、元メールMessage-IDをPUTで変更しようとした場合は拒否する。
- `SUMMARY`は空にできない。
- `DUE`は必須とする。
- `DTSTART`がある場合、同じ値種別に正規化した上で`DTSTART <= DUE`を要求する。
- 日付だけの値と日時値を区別し、既存値の精度を不必要に変換しない。
- 未対応プロパティは正本へ取り込まず、対応外であることを応答またはログで確認できるようにする。

## 7. 限定CalDAVの初回範囲

単一のWorkInBox締切collectionを提供する。初回に必要な操作は次とする。

- `OPTIONS`
- `PROPFIND`
- `REPORT`
- `GET`
- `PUT`

ThunderbirdからWIBで作成済みの締切を取得・編集することを目的とする。次は初回対象外とする。

- Thunderbirdからの新規ToDo作成
- Thunderbirdからの締切削除
- `MKCALENDAR`や複数collection
- 繰り返し、アラーム、参加者、添付、共有
- 競合内容の自動マージ

未対応の作成・削除要求は、成功したように見せず明示的に拒否する。

## 8. 競合、認証、公開範囲

- 各resourceへ安定したETagを付ける。
- 更新は`If-Match`を検証し、古いETagによるPUTを競合として拒否する。
- 後から届いた更新で無条件に上書きしない。
- 競合時はThunderbird側の再取得・再編集で解消する。自動マージは行わない。
- 認証方式、CalDAV URL、Thunderbirdへの登録手順は実装時に確定する。
- credentialはリポジトリ、VTODO、Extensionキャッシュへ保存しない。
- 書き込み可能なCalDAV endpointを認証なしで信頼境界外へ公開しない。

## 9. 現行`deadlines.ics`からの移行

- #32完了までは現行の読み取り専用`deadlines.ics`を使用する。
- CalDAV導入時に既存URLを直ちに削除せず、移行確認期間を設ける。
- 同じ締切を`deadlines.ics`とCalDAVの両方で登録すると二重表示になるため、利用者向け手順で旧購読を解除してからCalDAVを登録する。
- UIDは現行VTODOと同じ値を維持する。
- `mid:`元メールリンクが移行前後で機能することを確認する。

## 10. 完了条件

- Thunderbirdで既存締切のタイトル、着手日時、期限、メモ、完了、重要度を変更するとSQLiteへ反映される。
- WIB Webでタイトル、期限、メモを変更するとThunderbirdへ反映され、着手日時・完了・重要度は失われない。
- 競合更新が検知され、意図せず上書きされない。
- Extensionの期限超過・7日以内の件数がSQLiteの未完了締切と一致する。
- ExtensionからThunderbirdのToDo画面を開ける。
- `mid:`リンクから元メールを引き続き素早く開ける。
- 読み取り専用`deadlines.ics`から二重表示なく移行できる。

## 11. 実装時に決めること

- CalDAVの認証方式とURL
- Thunderbirdのアカウント登録・移行手順
- ETagの具体的な生成方法
- ExtensionからThunderbird ToDo画面を開くAPI差異と代替導線
- CalDAV非対応クライアントから不正値を受けた場合の具体的なHTTPエラー応答
