"""kyojuro_calendar.lib.lunar のテスト。

純粋数式、外部依存なし。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from skills.kyojuro_calendar.lib import lunar as ln


class TestComputePhaseValue:
    def test_reference_new_moon_returns_zero(self) -> None:
        # 基準新月 (2000-01-06 18:14 UTC) → phase ≈ 0.0
        ref = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
        phase = ln.compute_phase_value(ref)
        assert abs(phase) < 0.01 or abs(phase - 1.0) < 0.01

    def test_half_synodic_returns_full(self) -> None:
        # 基準新月から 14.77 日後 → phase ≈ 0.5 (満月相当)
        ref = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
        target = ref + timedelta(days=14.77)
        phase = ln.compute_phase_value(target)
        assert abs(phase - 0.5) < 0.01

    def test_quarter_synodic_returns_quarter(self) -> None:
        ref = datetime(2000, 1, 6, 18, 14, 0, tzinfo=timezone.utc)
        target = ref + timedelta(days=29.530588853 / 4)
        phase = ln.compute_phase_value(target)
        assert abs(phase - 0.25) < 0.01

    def test_naive_datetime_treated_as_utc(self) -> None:
        ref_naive = datetime(2000, 1, 6, 18, 14, 0)  # naive
        phase = ln.compute_phase_value(ref_naive)
        assert abs(phase) < 0.01 or abs(phase - 1.0) < 0.01

    def test_other_timezone_normalized(self) -> None:
        # JST = UTC+9。同じ瞬間を別 TZ で表しても結果は同じ
        from datetime import timezone as tz

        jst = tz(timedelta(hours=9))
        target_utc = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        target_jst = datetime(2025, 6, 1, 21, 0, 0, tzinfo=jst)
        assert abs(ln.compute_phase_value(target_utc) - ln.compute_phase_value(target_jst)) < 0.0001


class TestClassifyPhase:
    def test_zero_is_new_moon(self) -> None:
        assert ln.classify_phase(0.0) == ln.PHASE_NEW_MOON

    def test_one_is_new_moon(self) -> None:
        assert ln.classify_phase(0.99) == ln.PHASE_NEW_MOON

    def test_half_is_full_moon(self) -> None:
        assert ln.classify_phase(0.5) == ln.PHASE_FULL_MOON

    def test_quarter_is_first_quarter(self) -> None:
        assert ln.classify_phase(0.25) == ln.PHASE_FIRST_QUARTER

    def test_three_quarter_is_last_quarter(self) -> None:
        assert ln.classify_phase(0.75) == ln.PHASE_LAST_QUARTER

    def test_intermediate_waxing_crescent(self) -> None:
        assert ln.classify_phase(0.10) == ln.PHASE_WAXING_CRESCENT

    def test_intermediate_waxing_gibbous(self) -> None:
        assert ln.classify_phase(0.40) == ln.PHASE_WAXING_GIBBOUS

    def test_intermediate_waning_gibbous(self) -> None:
        assert ln.classify_phase(0.60) == ln.PHASE_WANING_GIBBOUS

    def test_intermediate_waning_crescent(self) -> None:
        assert ln.classify_phase(0.85) == ln.PHASE_WANING_CRESCENT

    def test_out_of_range_normalized(self) -> None:
        assert ln.classify_phase(1.5) == ln.PHASE_FULL_MOON  # 1.5 % 1.0 = 0.5


class TestComputeLunarPhase:
    def test_str_input(self) -> None:
        result = ln.compute_lunar_phase("2026-05-09")
        assert result.target_date == "2026-05-09"
        assert 0.0 <= result.phase_value < 1.0
        assert result.phase_key in ln.ALL_PHASES
        assert result.phase_label_ja in ln.PHASE_LABELS_JA.values()

    def test_date_input(self) -> None:
        result = ln.compute_lunar_phase(date(2026, 5, 10))
        assert result.target_date == "2026-05-10"

    def test_datetime_input(self) -> None:
        result = ln.compute_lunar_phase(
            datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        )
        assert result.target_date == "2026-05-10"

    def test_age_days_in_range(self) -> None:
        result = ln.compute_lunar_phase("2026-05-10")
        assert 0.0 <= result.age_days < 30.0

    def test_illumination_in_range(self) -> None:
        result = ln.compute_lunar_phase("2026-05-10")
        assert 0.0 <= result.illumination_percent <= 100.0

    def test_invalid_input_raises(self) -> None:
        with pytest.raises(TypeError):
            ln.compute_lunar_phase(12345)  # type: ignore[arg-type]


class TestIsHelpers:
    def test_is_new_moon_some_date(self) -> None:
        # 2026-04-17 は新月ではないかもしれないが、関数は bool を返す
        assert isinstance(ln.is_new_moon("2026-04-17"), bool)

    def test_is_full_moon_some_date(self) -> None:
        assert isinstance(ln.is_full_moon("2026-05-10"), bool)
