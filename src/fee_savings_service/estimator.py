from __future__ import annotations

from dataclasses import dataclass
import time

from fee_savings_service.hyperliquid_client import HyperliquidClient
from fee_savings_service.models import (
    CurrentRateSummary,
    SavingsEstimateResponse,
    VolumeWindow,
    WindowVolumeSummary,
)


def _to_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class PortfolioVolumes:
    day: float = 0.0
    week: float = 0.0
    month: float = 0.0
    all_time: float = 0.0
    perp_day: float = 0.0
    perp_week: float = 0.0
    perp_month: float = 0.0
    perp_all_time: float = 0.0


@dataclass
class FillSummary:
    requests_used: int = 0
    fill_count: int = 0
    total_fee: float = 0.0
    total_builder_fee: float = 0.0
    total_notional: float = 0.0
    crossed_notional: float = 0.0
    resting_notional: float = 0.0
    oldest_seen_ms: int | None = None
    newest_seen_ms: int | None = None
    exhausted: bool = False


class HyperliquidSavingsEstimator:
    def __init__(self, client: HyperliquidClient) -> None:
        self._client = client

    async def estimate(
        self,
        address: str,
        window: VolumeWindow,
        *,
        max_fill_requests: int = 1,
    ) -> SavingsEstimateResponse:
        user_fees_payload = await self._client.user_fees(address)
        portfolio_payload = await self._client.portfolio(address)
        now_ms = int(time.time() * 1000)
        start_ms = _window_start_ms(window, now_ms)
        fill_summary = await self._collect_fill_summary(
            address=address,
            start_ms=start_ms,
            end_ms=now_ms,
            max_requests=max_fill_requests,
        )

        rates = CurrentRateSummary(
            perp_taker_rate=_to_float(user_fees_payload.get("userCrossRate")),
            perp_maker_rate=_to_float(user_fees_payload.get("userAddRate")),
            spot_taker_rate=_to_float(user_fees_payload.get("userSpotCrossRate")),
            spot_maker_rate=_to_float(user_fees_payload.get("userSpotAddRate")),
        )

        daily_rows = user_fees_payload.get("dailyUserVlm", [])
        recent_cross_volume = 0.0
        recent_add_volume = 0.0
        if isinstance(daily_rows, list):
            for row in daily_rows:
                if not isinstance(row, dict):
                    continue
                recent_cross_volume += _to_float(row.get("userCross"))
                recent_add_volume += _to_float(row.get("userAdd"))

        summary_recent_total = recent_cross_volume + recent_add_volume
        if summary_recent_total > 0:
            summary_blended_perp_rate = (
                (recent_cross_volume * rates.perp_taker_rate)
                + (recent_add_volume * rates.perp_maker_rate)
            ) / summary_recent_total
        else:
            summary_blended_perp_rate = rates.perp_taker_rate

        if fill_summary.total_notional > 0:
            recent_blended_perp_rate = (
                (fill_summary.crossed_notional * rates.perp_taker_rate)
                + (fill_summary.resting_notional * rates.perp_maker_rate)
            ) / fill_summary.total_notional
            recent_cross_volume = fill_summary.crossed_notional
            recent_add_volume = fill_summary.resting_notional
            ratio_mode = "recent_fill_maker_taker_mix"
        elif summary_recent_total > 0:
            recent_blended_perp_rate = summary_blended_perp_rate
            ratio_mode = "user_fees_maker_taker_mix"
        else:
            recent_blended_perp_rate = rates.perp_taker_rate
            ratio_mode = "fallback_taker_only"

        portfolio_volumes = _parse_portfolio_volumes(portfolio_payload)
        requested_perp_volume = _requested_perp_volume(portfolio_volumes, window)
        requested_total_volume = _requested_total_volume(portfolio_volumes, window)
        exact_fill_coverage = _has_exact_fill_coverage(fill_summary, start_ms, requested_perp_volume)

        if exact_fill_coverage:
            estimated_hl_fees_paid = fill_summary.total_fee
            fully_covered = True
            estimation_mode = "exact_from_fill_fees"
            coverage_note = "Exact fee total from Hyperliquid fills for the requested window."
        elif window in {VolumeWindow.ONE_DAY, VolumeWindow.SEVEN_DAYS} and summary_recent_total > 0:
            exact_cross, exact_add, fully_covered = _windowed_recent_volumes(daily_rows, window)
            estimated_hl_fees_paid = (
                exact_cross * rates.perp_taker_rate
                + exact_add * rates.perp_maker_rate
            )
            estimation_mode = "estimate_from_user_fees_daily_breakdown"
            coverage_note = (
                "Estimated from userFees daily volume and current perp maker/taker rates."
                if fully_covered
                else "Requested window extends beyond the available userFees daily history."
            )
        else:
            estimated_hl_fees_paid = requested_perp_volume * recent_blended_perp_rate
            fully_covered = False
            estimation_mode = f"portfolio_volume_with_{ratio_mode}"
            if fill_summary.total_notional > 0:
                coverage_note = (
                    "Computed from Hyperliquid portfolio perp volume and a blended current perp rate "
                    f"derived from {fill_summary.fill_count} recent fills across "
                    f"{fill_summary.requests_used} fill request(s)."
                )
            else:
                coverage_note = (
                    "Computed from Hyperliquid portfolio perp volume and a blended current perp rate derived "
                    "from recent userFees maker/taker mix."
                )

        methodology_note = (
            "Savings assume Lighter Standard Accounts with zero trading fees. "
            "When enough fill history is available, this uses exact Hyperliquid fill fees. "
            "Otherwise it estimates from perp portfolio volume and recent maker/taker mix."
        )

        return SavingsEstimateResponse(
            address=address,
            window=window,
            estimated_hl_fees_paid=estimated_hl_fees_paid,
            estimated_savings=estimated_hl_fees_paid,
            fee_assumption="Lighter Standard Accounts: 0 maker / 0 taker",
            estimation_mode=estimation_mode,
            methodology_note=methodology_note,
            current_rates=rates,
            recent_cross_volume=recent_cross_volume,
            recent_add_volume=recent_add_volume,
            recent_blended_perp_rate=recent_blended_perp_rate,
            requested_perp_volume=requested_perp_volume,
            requested_total_volume=requested_total_volume,
            portfolio_windows=WindowVolumeSummary(
                day=portfolio_volumes.day,
                week=portfolio_volumes.week,
                month=portfolio_volumes.month,
                all_time=portfolio_volumes.all_time,
            ),
            max_fill_requests=max_fill_requests,
            fill_requests_used=fill_summary.requests_used,
            fill_count=fill_summary.fill_count,
            fill_coverage_oldest_ms=fill_summary.oldest_seen_ms,
            fill_coverage_newest_ms=fill_summary.newest_seen_ms,
            fully_covered=fully_covered,
            coverage_note=coverage_note,
        )

    async def _collect_fill_summary(
        self,
        *,
        address: str,
        start_ms: int,
        end_ms: int,
        max_requests: int,
    ) -> FillSummary:
        summary = FillSummary()
        next_start_ms = start_ms
        seen: set[tuple[object, ...]] = set()

        for _ in range(max_requests):
            rows = await self._client.user_fills_by_time(
                address,
                next_start_ms,
                end_ms,
                aggregate_by_time=False,
            )
            summary.requests_used += 1
            if not rows:
                break

            max_time: int | None = None
            new_rows = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_key = (
                    row.get("hash"),
                    row.get("oid"),
                    row.get("tid"),
                    row.get("time"),
                    row.get("coin"),
                    row.get("px"),
                    row.get("sz"),
                    row.get("fee"),
                )
                if row_key in seen:
                    continue
                seen.add(row_key)
                new_rows += 1

                timestamp = int(_to_float(row.get("time")))
                if timestamp <= 0:
                    continue

                notional = _to_float(row.get("px")) * _to_float(row.get("sz"))
                summary.fill_count += 1
                summary.total_fee += _to_float(row.get("fee"))
                summary.total_builder_fee += _to_float(row.get("builderFee"))
                summary.total_notional += notional
                if row.get("crossed") is True:
                    summary.crossed_notional += notional
                else:
                    summary.resting_notional += notional

                summary.oldest_seen_ms = (
                    timestamp
                    if summary.oldest_seen_ms is None
                    else min(summary.oldest_seen_ms, timestamp)
                )
                summary.newest_seen_ms = (
                    timestamp
                    if summary.newest_seen_ms is None
                    else max(summary.newest_seen_ms, timestamp)
                )
                max_time = timestamp if max_time is None else max(max_time, timestamp)

            if len(rows) < 2000 or max_time is None or max_time >= end_ms or new_rows == 0:
                summary.exhausted = True
                break
            next_start_ms = max_time + 1

        return summary


def _parse_portfolio_volumes(payload: list[object]) -> PortfolioVolumes:
    mapping: dict[str, float] = {}
    for row in payload:
        if not isinstance(row, list) or len(row) != 2:
            continue
        window = str(row[0])
        if not isinstance(row[1], dict):
            continue
        mapping[window] = _to_float(row[1].get("vlm"))
    return PortfolioVolumes(
        day=mapping.get("day", 0.0),
        week=mapping.get("week", 0.0),
        month=mapping.get("month", 0.0),
        all_time=mapping.get("allTime", 0.0),
        perp_day=mapping.get("perpDay", 0.0),
        perp_week=mapping.get("perpWeek", 0.0),
        perp_month=mapping.get("perpMonth", 0.0),
        perp_all_time=mapping.get("perpAllTime", 0.0),
    )


def _windowed_recent_volumes(daily_rows: object, window: VolumeWindow) -> tuple[float, float, bool]:
    if not isinstance(daily_rows, list):
        return 0.0, 0.0, False

    requested_days = 1 if window == VolumeWindow.ONE_DAY else 7
    usable_rows = [row for row in daily_rows if isinstance(row, dict)]
    subset = usable_rows[-requested_days:]
    fully_covered = len(subset) == requested_days

    cross = sum(_to_float(row.get("userCross")) for row in subset)
    add = sum(_to_float(row.get("userAdd")) for row in subset)
    return cross, add, fully_covered


def _window_start_ms(window: VolumeWindow, now_ms: int) -> int:
    day_ms = 24 * 60 * 60 * 1000
    if window == VolumeWindow.ONE_DAY:
        return now_ms - day_ms
    if window == VolumeWindow.SEVEN_DAYS:
        return now_ms - 7 * day_ms
    if window == VolumeWindow.THIRTY_DAYS:
        return now_ms - 30 * day_ms
    return 0


def _has_exact_fill_coverage(fill_summary: FillSummary, start_ms: int, requested_perp_volume: float) -> bool:
    if not fill_summary.exhausted:
        return False
    if requested_perp_volume <= 0:
        return fill_summary.fill_count == 0 or fill_summary.total_notional <= 1e-9
    if fill_summary.total_notional <= 0:
        return False

    relative_gap = abs(fill_summary.total_notional - requested_perp_volume) / requested_perp_volume
    if relative_gap <= 0.01:
        return True

    if fill_summary.oldest_seen_ms is None:
        return False
    return fill_summary.oldest_seen_ms <= start_ms + 1000


def _requested_perp_volume(portfolio_volumes: PortfolioVolumes, window: VolumeWindow) -> float:
    if window == VolumeWindow.ONE_DAY:
        return portfolio_volumes.perp_day
    if window == VolumeWindow.SEVEN_DAYS:
        return portfolio_volumes.perp_week
    if window == VolumeWindow.THIRTY_DAYS:
        return portfolio_volumes.perp_month
    return portfolio_volumes.perp_all_time


def _requested_total_volume(portfolio_volumes: PortfolioVolumes, window: VolumeWindow) -> float:
    if window == VolumeWindow.ONE_DAY:
        return portfolio_volumes.day
    if window == VolumeWindow.SEVEN_DAYS:
        return portfolio_volumes.week
    if window == VolumeWindow.THIRTY_DAYS:
        return portfolio_volumes.month
    return portfolio_volumes.all_time
