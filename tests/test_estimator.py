from fee_savings_service.estimator import (
    FillSummary,
    _has_exact_fill_coverage,
    _parse_portfolio_volumes,
    _window_start_ms,
    _windowed_recent_volumes,
)
from fee_savings_service.models import VolumeWindow


def test_parse_portfolio_volumes() -> None:
    volumes = _parse_portfolio_volumes(
        [
            ["day", {"vlm": "1"}],
            ["week", {"vlm": "2"}],
            ["month", {"vlm": "3"}],
            ["allTime", {"vlm": "4"}],
            ["perpDay", {"vlm": "5"}],
            ["perpWeek", {"vlm": "6"}],
            ["perpMonth", {"vlm": "7"}],
            ["perpAllTime", {"vlm": "8"}],
        ]
    )
    assert volumes.day == 1.0
    assert volumes.week == 2.0
    assert volumes.month == 3.0
    assert volumes.all_time == 4.0
    assert volumes.perp_day == 5.0
    assert volumes.perp_week == 6.0
    assert volumes.perp_month == 7.0
    assert volumes.perp_all_time == 8.0


def test_windowed_recent_volumes_for_week() -> None:
    rows = [
        {"userCross": "1", "userAdd": "2"},
        {"userCross": "3", "userAdd": "4"},
        {"userCross": "5", "userAdd": "6"},
        {"userCross": "7", "userAdd": "8"},
        {"userCross": "9", "userAdd": "10"},
        {"userCross": "11", "userAdd": "12"},
        {"userCross": "13", "userAdd": "14"},
    ]
    cross, add, covered = _windowed_recent_volumes(rows, VolumeWindow.SEVEN_DAYS)
    assert cross == 49.0
    assert add == 56.0
    assert covered is True


def test_window_start_ms_for_thirty_days() -> None:
    now_ms = 1_000_000
    assert _window_start_ms(VolumeWindow.THIRTY_DAYS, now_ms) == now_ms - 30 * 24 * 60 * 60 * 1000


def test_exact_fill_coverage_requires_full_window() -> None:
    summary = FillSummary(
        oldest_seen_ms=10_000,
        newest_seen_ms=20_000,
        total_notional=100.5,
        exhausted=True,
    )
    assert _has_exact_fill_coverage(summary, 10_000, 100.0) is True
    assert _has_exact_fill_coverage(summary, 8_000, 100.0) is True
    assert _has_exact_fill_coverage(FillSummary(oldest_seen_ms=10_000, newest_seen_ms=20_000), 10_000, 100.0) is False
