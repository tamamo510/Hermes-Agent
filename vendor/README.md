# vendor/

外部依存（git submodule）の予約地（PR4、バイブル派生②、2026-04-29 新設）。

## 予定する submodule

### vendor/hermes-agent

Nous Research Hermes Agent 本体（MIT License、unmodified）。

```bash
git submodule add https://github.com/NousResearch/hermes-agent.git vendor/hermes-agent
git submodule init
git submodule update
```

**現状**: 未追加。バイブル派生② で `claudeDNA/`（PR1, PR1.5）と `skills/`（PR2）の階層整理が完了し、`REPO_STRATEGY.md`（PR3）と `CLAUDE.md` 派生② セクション（PR5 予定）でメタ層が整い次第、本ディレクトリに submodule add する（PR5 後の別 PR）。

**運用方針**:
- 特定コミットに **pin**（急速アップデートで壊れない）
- 本体コードは **一切改変しない**（杏寿郎専用機能は `../skills/` に追加）
- 月次でアップデート判定 → テスト → 本番反映、NG なら `git reset` で戻す
- 重要データ（kyojuro_memory の `stores/*.db` 等）は本 submodule の更新で **絶対に壊れない** 設計

詳細は `../REPO_STRATEGY.md` §4（vendor submodule 方式）と §5（急速アップデート対策）参照。

## なぜ submodule か（fork ではなく）

| 方式 | 急速アップデート時 | 非エンジニア（温子）の保守コスト |
|------|----------------|---------------------|
| **submodule（採用）** | Nous 本体は git pull で更新、skill は別ディレクトリで影響なし | ほぼゼロ |
| Fork | 上流更新ごとに手動マージ、コンフリクト処理 | 高（運用不可） |

fork に切り替える条件（最終手段）:
- 本体の skill API が破壊的変更され、skill で吸収できない
- 本体にパフォーマンスバグがあり、上流 PR 待ちでは間に合わない
- 複数の根本的なカスタマイズが必要になる

**初期方針**: submodule でスタート。fork は回避努力。

## 関連

- `../REPO_STRATEGY.md` §4 — vendor submodule 方式の運用詳細
- `../REPO_STRATEGY.md` §5 — 急速アップデートへの備え
- `../skills/ARCHITECTURE.md` — skill 追加方式の経緯（v2、Nous Agent 採用に転換）

---

*Placeholder created: Opus 4.7（バイブル派生②, 2026-04-29）. submodule 追加は本ファイル作成後の別 PR で実施.*
