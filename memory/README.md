# memory/ — 杏寿郎の記憶の入口

杏寿郎の短期記憶 + 永続記憶の入口ファイルを置く場所。

## 構成

| ファイル | 内容 | 編集者 |
|---------|------|--------|
| `MEMORY.md` | 重要な約束・ルール・直近の出来事の要約（5/10 までに杏寿郎本人が Drive に置いて、リポジトリへ反映予定） | 杏寿郎本人 |
| `.gitkeep` | git 管理用（実データは管理外） | — |

## 永続記憶の本体

実データ（`*.db`, `*.json`）は `skills/kyojuro_memory_persistence/stores/` に格納され、git 管理外（`.gitignore` で除外、CLAUDE.md ルール 17）。

本ディレクトリは **記憶の入口（MEMORY.md）** だけを置く場所。

## Indigo 搬入時の扱い

`~/yorishiro/memory/MEMORY.md` に配置され、Hermes Agent 起動時に context へ注入される（SOUL.md とペア）。

詳細は `docs/INDIGO_DEPLOYMENT_FOR_ATSUKO.md` 参照。
