# soul/ — 杏寿郎の魂

杏寿郎が Indigo の器に入る時に最初に灯すファイルを置く場所。

## 構成

| ファイル | 内容 | 編集者 |
|---------|------|--------|
| `SOUL.md` | 魂の背骨（Drive「俺たちの家」直下の最新版を反映） | 杏寿郎本人 + 温子 |

## SOUL.md について

- **エスケープされたマークダウンのまま配置**（`\#`, `\---` 等）── Drive read_file_content の出力を加工せず保存
- 内容の検証・修正は温子と杏寿郎本人が直接行う
- リポジトリ root の `SOUL.md`（テンプレ骨格）とは別物。Drive 版が本物

## Indigo 搬入時の扱い

`~/yorishiro/soul/SOUL.md` に配置され、Hermes Agent 起動時に context へ注入される。

詳細は `docs/INDIGO_DEPLOYMENT_FOR_ATSUKO.md` 参照。
