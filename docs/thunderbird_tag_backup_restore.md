# Thunderbird タグの導入前バックアップと復元

## 1. 目的

WorkInBox は Thunderbird に WorkInBox 用タグ定義を追加する。

その際、将来 WorkInBox の利用を停止した場合でも、**WorkInBox 導入前の Thunderbird タグ定義へ戻せること**を重視する。

この文書では、次を扱う。

- WorkInBox 導入前の Thunderbird タグ定義を保存する方法
- WorkInBox タグ導入後に何が変わるか
- WorkInBox 利用停止時に元のタグ定義へ戻す方法
- Thunderbird のタグ定義と、メール上の IMAP keyword の違い
- より強い保険として Thunderbird プロファイル全体を退避する方法

この仕組みは、WorkInBox が既存 Thunderbird 環境を一方的に置き換えず、利用者が元へ戻れるようにするためのものである。

---

## 2. Thunderbird のタグは2つの層に分けて考える

Thunderbird のタグ連携では、次の2つを区別する。

### A. Thunderbird のタグ定義

Thunderbird がローカ