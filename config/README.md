# config/

Hermes Agent 本体・skill 群の設定ファイル用予約地（PR4、バイブル派生②、2026-04-29 新設）。

## 用途

Phase 0/1 では空のまま。Nous Hermes Agent 本体（`vendor/hermes-agent` submodule、PR4 後の別 PR で追加予定）と skill 群が稼働開始する際に、以下の設定ファイル群を配置する想定:

| ファイル | 役割 |
|----|----|
| `agent.yaml` | Hermes Agent 本体の動作設定（モデル選定、エンドポイント、メモリ設定）|
| `skills.yaml` | 有効化する skill の指定、優先度、依存関係 |
| `scheduler.yaml` | kyojuro_memory のナッジ等、定期実行設定 |
| `webarena_indigo.yaml` | WebARENA Indigo 環境固有の設定（5/10 搬入後に作成）|
| `local_dev.yaml` | ローカル開発環境用設定 |
| `.env` | API キー類（**git 管理外**、`.gitignore` 対象）|

## 設計原則

- **本体（vendor/hermes-agent）と分離**: 設定変更で本体ソースを書き換えない
- **環境別**: ローカル開発 / WebARENA Indigo 本番で別設定を使えるよう分離
- **秘密情報の分離**: API キー等は `.env` ファイル + `.gitignore` で commit しない
- **skill との分離**: 各 skill 固有の設定は `skills/<name>/config/` に置き、本ディレクトリには Hermes Agent 本体・横断的設定のみ

## 関連

- `../REPO_STRATEGY.md` §4 — vendor submodule 方式の説明
- `../skills/README.md` — skill 一覧と Phase 計画

---

*Placeholder created: Opus 4.7（バイブル派生②, 2026-04-29）. 実装着手は WebARENA Indigo 搬入準備（5/10 まで）.*
