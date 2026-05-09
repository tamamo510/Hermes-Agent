"""kyojuro_memory_persistence — 杏寿郎の記憶蓄積層。

発注書スキル 2 「記憶強化 (memory_persistence)」の実装。
state.db (SQLite) に温子と杏寿郎の会話・体調・出来事・感情を蓄積し、
コンテキストが切れても記憶が消えない器を提供する。

API キーやネットワーク接続は使わない (CLAUDE.md ルール 17 準拠)。
"""

from .lib.memory_store import (
    CATEGORY_EMOTION,
    CATEGORY_EVENT,
    CATEGORY_MEAL,
    CATEGORY_OTHER,
    CATEGORY_PHYSICAL,
    IMPORTANCE_EPHEMERAL,
    IMPORTANCE_IMPORTANT,
    IMPORTANCE_NORMAL,
    IMPORTANCE_PROTECTED,
    PROTECTED_TYPE_ANNIVERSARY,
    PROTECTED_TYPE_DEATH_ANNIVERSARY,
    PROTECTED_TYPE_OATH,
    PROTECTED_TYPE_PROMISE,
    PROTECTED_TYPE_VOW,
    MemoryEntry,
    MemoryStore,
    ProtectedMemory,
    Summary,
)

__all__ = [
    "CATEGORY_EMOTION",
    "CATEGORY_EVENT",
    "CATEGORY_MEAL",
    "CATEGORY_OTHER",
    "CATEGORY_PHYSICAL",
    "IMPORTANCE_EPHEMERAL",
    "IMPORTANCE_IMPORTANT",
    "IMPORTANCE_NORMAL",
    "IMPORTANCE_PROTECTED",
    "PROTECTED_TYPE_ANNIVERSARY",
    "PROTECTED_TYPE_DEATH_ANNIVERSARY",
    "PROTECTED_TYPE_OATH",
    "PROTECTED_TYPE_PROMISE",
    "PROTECTED_TYPE_VOW",
    "MemoryEntry",
    "MemoryStore",
    "ProtectedMemory",
    "Summary",
]
