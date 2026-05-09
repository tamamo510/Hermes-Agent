"""kyojuro_calendar.lib.anniversaries のテスト。

ビルトイン記念日 + カスタム記念日の管理を網羅。
"""

from __future__ import annotations

from datetime import date

import pytest

from skills.kyojuro_calendar.lib import anniversaries as ann


class TestBuiltinAnniversaries:
    def test_all_seven_present(self) -> None:
        # 発注書 §5-3 の 7 つが含まれている
        mmdds = {a.mmdd for a in ann.BUILTIN_ANNIVERSARIES}
        for required in ["01-31", "02-05", "04-17", "05-10", "05-28", "07-31", "10-05"]:
            assert required in mmdds

    def test_kyojuro_birthday_includes_special(self) -> None:
        for a in ann.BUILTIN_ANNIVERSARIES:
            if a.mmdd == "05-10":
                assert "母の日" in a.title or "魂入れ" in a.title

    def test_atsuko_birthday_includes_wedding(self) -> None:
        for a in ann.BUILTIN_ANNIVERSARIES:
            if a.mmdd == "02-05":
                assert "誕生日" in a.title or "結婚" in a.title

    def test_aisai_day_marked_as_family(self) -> None:
        for a in ann.BUILTIN_ANNIVERSARIES:
            if a.mmdd == "01-31":
                assert a.type == ann.TYPE_FAMILY_DAY

    def test_death_anniversaries_typed_correctly(self) -> None:
        for a in ann.BUILTIN_ANNIVERSARIES:
            if a.mmdd in ("04-17", "05-28", "07-31"):
                assert a.type == ann.TYPE_DEATH


class TestRegistryMatchesOn:
    def test_matches_kyojuro_birthday(self) -> None:
        registry = ann.AnniversaryRegistry()
        matches = registry.matches_on("2026-05-10")
        assert len(matches) == 1
        assert "杏寿郎" in matches[0].title or "誕生日" in matches[0].title
        assert matches[0].is_builtin is True

    def test_matches_haha_no_meinichi(self) -> None:
        registry = ann.AnniversaryRegistry()
        matches = registry.matches_on("2026-05-28")
        assert len(matches) == 1
        assert "母上" in matches[0].title
        assert matches[0].type == ann.TYPE_DEATH

    def test_no_match_returns_empty(self) -> None:
        registry = ann.AnniversaryRegistry()
        assert registry.matches_on("2026-06-15") == []

    def test_matches_year_independent(self) -> None:
        registry = ann.AnniversaryRegistry()
        m_2026 = registry.matches_on("2026-05-10")
        m_2027 = registry.matches_on("2027-05-10")
        assert len(m_2026) == len(m_2027) == 1

    def test_matches_with_date_object(self) -> None:
        registry = ann.AnniversaryRegistry()
        matches = registry.matches_on(date(2026, 5, 10))
        assert len(matches) == 1


class TestRegistryAdd:
    def test_add_custom(self) -> None:
        registry = ann.AnniversaryRegistry()
        registry.add(mmdd="06-15", title="温子のお父様の誕生日")
        matches = registry.matches_on("2026-06-15")
        assert len(matches) == 1
        assert matches[0].title == "温子のお父様の誕生日"
        assert matches[0].is_builtin is False

    def test_add_with_type(self) -> None:
        registry = ann.AnniversaryRegistry()
        registry.add(
            mmdd="06-15", title="特別な日", type=ann.TYPE_OATH, notes="2026 年から"
        )
        matches = registry.matches_on("2026-06-15")
        assert matches[0].type == ann.TYPE_OATH
        assert matches[0].notes == "2026 年から"

    def test_invalid_mmdd_raises(self) -> None:
        registry = ann.AnniversaryRegistry()
        with pytest.raises(ValueError):
            registry.add(mmdd="2026-06-15", title="フル日付")
        with pytest.raises(ValueError):
            registry.add(mmdd="13-50", title="存在しない日")
        with pytest.raises(ValueError):
            registry.add(mmdd="", title="空")

    def test_empty_title_raises(self) -> None:
        registry = ann.AnniversaryRegistry()
        with pytest.raises(ValueError):
            registry.add(mmdd="06-15", title="")
        with pytest.raises(ValueError):
            registry.add(mmdd="06-15", title="   ")


class TestRegistryListAll:
    def test_lists_only_builtins_when_empty(self) -> None:
        registry = ann.AnniversaryRegistry()
        all_anns = registry.list_all()
        assert len(all_anns) == len(ann.BUILTIN_ANNIVERSARIES)

    def test_lists_builtin_plus_custom(self) -> None:
        registry = ann.AnniversaryRegistry()
        registry.add(mmdd="06-15", title="カスタム")
        all_anns = registry.list_all()
        assert len(all_anns) == len(ann.BUILTIN_ANNIVERSARIES) + 1


class TestRegistryUpcoming:
    def test_upcoming_within_7_days(self) -> None:
        registry = ann.AnniversaryRegistry()
        # 5/9 から 7 日以内 → 5/10 (杏寿郎誕生日) が含まれる
        upcoming = registry.upcoming_within(days=7, today="2026-05-09")
        labels = [label for label, _ in upcoming]
        # 5/10 = 明日
        assert any(l == "明日" for l in labels)

    def test_upcoming_today(self) -> None:
        registry = ann.AnniversaryRegistry()
        upcoming = registry.upcoming_within(days=0, today="2026-05-10")
        # 5/10 = 今日
        assert any(label == "今日" for label, _ in upcoming)

    def test_upcoming_far_window(self) -> None:
        registry = ann.AnniversaryRegistry()
        # 5/9 から 30 日 → 5/28 (母上の命日) も含まれる
        upcoming = registry.upcoming_within(days=30, today="2026-05-09")
        titles = [a.title for _, a in upcoming]
        assert any("母上" in t for t in titles)

    def test_upcoming_no_match(self) -> None:
        registry = ann.AnniversaryRegistry()
        # 11/1 から 7 日以内 → 該当なし (10/5 はもう過ぎ、12 月にもない)
        upcoming = registry.upcoming_within(days=7, today="2026-11-15")
        assert upcoming == []

    def test_invalid_days_raises(self) -> None:
        registry = ann.AnniversaryRegistry()
        with pytest.raises(ValueError):
            registry.upcoming_within(days=-1, today="2026-05-09")
