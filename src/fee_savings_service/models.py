from enum import Enum

from pydantic import BaseModel, Field


class VolumeWindow(str, Enum):
    ONE_DAY = "1d"
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    ALL_TIME = "all"


class SavingsEstimateRequest(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    window: VolumeWindow
    max_fill_requests: int | None = Field(default=None, ge=1, le=50)


class CurrentRateSummary(BaseModel):
    perp_taker_rate: float
    perp_maker_rate: float
    spot_taker_rate: float
    spot_maker_rate: float


class WindowVolumeSummary(BaseModel):
    day: float
    week: float
    month: float
    all_time: float


class SavingsEstimateResponse(BaseModel):
    address: str
    window: VolumeWindow
    estimated_hl_fees_paid: float
    estimated_savings: float
    fee_assumption: str
    estimation_mode: str
    methodology_note: str
    current_rates: CurrentRateSummary
    recent_cross_volume: float
    recent_add_volume: float
    recent_blended_perp_rate: float
    requested_perp_volume: float
    requested_total_volume: float
    portfolio_windows: WindowVolumeSummary
    max_fill_requests: int
    fill_requests_used: int
    fill_count: int
    fill_coverage_oldest_ms: int | None
    fill_coverage_newest_ms: int | None
    fully_covered: bool
    coverage_note: str


class HealthResponse(BaseModel):
    ok: bool
