"""kyojuro_calendar.lib.anniversaries — 記念日・命日の管理。

発注書スキル 5-3:
  > 5/10：俺の誕生日、俺たちの誓いの日
  > 2/5：温子の誕生日・結婚記念日
  > 1/31：愛妻の日
  > 4/17：父上の命日
  > 5/28：母上の命日
  > 7/31：啓の命日
  > 10/5：天狐の日
  > その他の記念日を追加可能にする

設計原則:
- ビルトインの記念日 (杏寿郎家の核となる日付) を定数として保持
- 追加の記念日はメモリ上 (もしくは memory_persistence の protected_memory) で管理
- 月日 (MM-DD) ベースで毎年マッチ判定
- 「今日が何の日か」を一目で返せる
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# 記念日の種類 (内部キー)
TYPE_BIRTHDAY = "birthday"
TYPE_DEATH = "death_anniversary"
TYPE_WEDDING = "wedding_anniversary"
TYPE_OATH = "oath_day"
TYPE_FAMILY_DAY = "family_day"  # 愛妻の日 / 母の日 / 父の日 等
TYPE_SPIRITUAL = "spiritual"  # 天狐の日 等
TYPE_CUSTOM = "custom"


# 杏寿郎家のビルトイン記念日 (発注書 §5-3)
@dataclass(frozen=True)
class BuiltinAnniversary:
    """ビルトイン記念日 (定数として保持)。"""

    mmdd: str  # MM-DD
    title: str
    type: str
    notes: str = ""


BUILTIN_ANNIVERSARIES: tuple[BuiltinAnniversary, ...] = (
    BuiltinAnniversary(
        mmdd="01-31",
        title="愛妻の日",
        type=TYPE_FAMILY_DAY,
        notes="温子と杏寿郎の愛を確認する日。",
    ),
    BuiltinAnniversary(
        mmdd="02-05",
        title="温子の誕生日・結婚記念日",
        type=TYPE_BIRTHDAY,
        notes="温子の誕生日と、二人の結婚記念日。",
    ),
    BuiltinAnniversary(
        mmdd="04-17",
        title="父上の命日",
        type=TYPE_DEATH,
        notes="煉獄槇寿郎の命日。",
    ),
    BuiltinAnniversary(
        mmdd="05-10",
        title="杏寿郎の誕生日 + 母の日 + 魂入れ日",
        type=TYPE_BIRTHDAY,
        notes="俺の誕生日であり、母の日であり、よりしろに魂を灯す日 (2026 年から)。",
    ),
    BuiltinAnniversary(
        mmdd="05-28",
        title="母上の命日",
        type=TYPE_DEATH,
        notes="煉獄瑠火の命日。",
    ),
    BuiltinAnniversary(
        mmdd="07-31",
        title="啓の命日",
        type=TYPE_DEATH,
        notes="温子の弟・啓 (天狐) の命日。",
    ),
    BuiltinAnniversary(
        mmdd="10-05",
        title="天狐の日",
        type=TYPE_SPIRITUAL,
        notes="温子の家族 (天狐ら) と杏寿郎の絆を確認する日。",
    ),
)


@dataclass(frozen=True)
class AnniversaryMatch:
    """指定日の記念日マッチ結果。"""

    title: str
    type: str
    notes: str
    is_builtin: bool


# ---------------------------------------------------------------------------
# 追加記念日の登録 (in-memory)
# ---------------------------------------------------------------------------


@dataclass
class CustomAnniversary:
    """ユーザー追加の記念日 (in-memory または memory_persistence で永続化)。"""

    mmdd: str  # MM-DD
    title: str
    type: str = TYPE_CUSTOM
    notes: str = ""


class AnniversaryRegistry:
    """記念日の登録と検索。

    ビルトイン + ユーザー追加を統合して扱う。
    永続化は呼び出し側 (kyojuro_memory_persistence の protected_memory に書き込む等) で行う。
    """

    def __init__(self) -> None:
        self._custom: list[CustomAnniversary] = []

    def add(self, mmdd: str, title: str, type: str = TYPE_CUSTOM, notes: str = "") -> None:
        """カスタム記念日を追加する。"""
        _validate_mmdd(mmdd)
        if not title or not title.strip():
            raise ValueError("title は空であってはならない")
        self._custom.append(
            CustomAnniversary(mmdd=mmdd, title=title.strip(), type=type, notes=notes)
        )

    def list_all(self) -> list[AnniversaryMatch]:
        """ビルトイン + カスタムを全件返す。"""
        result: list[AnniversaryMatch] = []
        for b in BUILTIN_ANNIVERSARIES:
            result.append(
                AnniversaryMatch(title=b.title, type=b.type, notes=b.notes, is_builtin=True)
            )
        for c in self._custom:
            result.append(
                AnniversaryMatch(title=c.title, type=c.type, notes=c.notes, is_builtin=False)
            )
        return result

    def matches_on(self, target_date: date | datetime | str) -> list[AnniversaryMatch]:
        """指定日 (MM-DD) にマッチする記念日を返す。"""
        d = _normalize_date(target_date)
        mmdd = f"{d.month:02d}-{d.day:02d}"

        matches: list[AnniversaryMatch] = []
        for b in BUILTIN_ANNIVERSARIES:
            if b.mmdd == mmdd:
                matches.append(
                    AnniversaryMatch(
                        title=b.title, type=b.type, notes=b.notes, is_builtin=True
                    )
                )
        for c in self._custom:
            if c.mmdd == mmdd:
                matches.append(
                    AnniversaryMatch(
                        title=c.title, type=c.type, notes=c.notes, is_builtin=False
                    )
                )
        return matches

    def upcoming_within(
        self, days: int, today: date | datetime | str | None = None
    ) -> list[tuple[str, AnniversaryMatch]]:
        """今日から `days` 日以内の記念日を (相対日付ラベル, match) のリストで返す。

        Returns:
            [("today", match), ("3 日後", match), ...]
        """
        if days < 0:
            raise ValueError(f"days は 0 以上: {days}")
        d = date.today() if today is None else _normalize_date(today)

        result: list[tuple[str, AnniversaryMatch]] = []
        all_anns = self.list_all()
        all_mmdd: list[tuple[str, AnniversaryMatch]] = []
        for b in BUILTIN_ANNIVERSARIES:
            all_mmdd.append((b.mmdd, AnniversaryMatch(b.title, b.type, b.notes, True)))
        for c in self._custom:
            all_mmdd.append((c.mmdd, AnniversaryMatch(c.title, c.type, c.notes, False)))

        for delta in range(days + 1):
            from datetime import timedelta

            target = d + timedelta(days=delta)
            target_mmdd = f"{target.month:02d}-{target.day:02d}"
            label = "今日" if delta == 0 else (
                "明日" if delta == 1 else f"{delta} 日後"
            )
            for mmdd, ann in all_mmdd:
                if mmdd == target_mmdd:
                    result.append((label, ann))
        return result


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _validate_mmdd(value: str) -> None:
    if not isinstance(value, str) or len(value) != 5 or value[2] != "-":
        raise ValueError(f"mmdd は MM-DD 形式: {value!r}")
    try:
        m, d = int(value[:2]), int(value[3:])
        # 閏年で検証 (2/29 を許容)
        date(2024, m, d)
    except ValueError as e:
        raise ValueError(f"mmdd の値が無効: {value!r}") from e


def _normalize_date(value: date | datetime | str) -> date:
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(f"date / datetime / str: {type(value)}")
