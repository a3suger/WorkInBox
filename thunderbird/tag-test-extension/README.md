# WorkInBox Thunderbird tag interop test extension

`docs/tag_test.md` の最初の相互運用テスト用 MailExtension です。

この extension は Thunderbird に次のタグ定義を1つだけ登録します。

| 項目 | 値 |
| --- | --- |
| key | `wib-deadline` |
| 表示名 | `締切あり` |
| 色 | `#d9534f` |

既に `wib-deadline` が存在する場合は、新しいタグを重複作成せず、表示名と色を上記の値に合わせます。
それ以外の Thunderbird タグには触れません。

## 対応 Thunderbird

Thunderbird 128 以上を対象にしています。
`messages.tags` API の `create()`, `list()`, `update()` を使用します。

## 一時的に読み込む

開発用の確認では、Thunderbird の Add-ons Debugging からこのディレクトリの `manifest.json` を一時的に読み込みます。

1. このリポジトリを `git pull` する。
2. Thunderbird で Add-ons Debugging を開く。
3. `Load Temporary Add-on...` を選ぶ。
4. `thunderbird/tag-test-extension/manifest.json` を選択する。
5. Thunderbird のタグ一覧に `締切あり` が現れることを確認する。

一時アドオンの具体的な開き方は Thunderbird のバージョンにより表示が多少異なることがあります。

## 次のテスト

タグが表示されたら `docs/tag_test.md` に従って、テストメールへ `締切あり` を付けます。

その後 WorkInBox の診断コマンドで IMAP FLAGS を確認します。

```bash
workinbox-imap-flags --config config.yaml --uid 12345
```

期待する keyword:

```text
wib-deadline
```

Thunderbird で `締切あり` を外した後、同じ診断コマンドを実行し、`wib-deadline` が消えることも確認します。

## この extension がしないこと

- メールへ自動的にタグを付けない。
- メールからタグを削除しない。
- WorkInBox 管理外のタグを変更しない。
- 12種類すべての WorkInBox タグをまだ登録しない。
- IMAP を直接操作しない。

まず `wib-deadline` 1タグで相互運用が成立することを確認してから、正式なタグ定義へ展開します。
