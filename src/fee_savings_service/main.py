from __future__ import annotations
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fee_savings_service.config import settings
from fee_savings_service.estimator import HyperliquidSavingsEstimator
from fee_savings_service.hyperliquid_client import HyperliquidClient
from fee_savings_service.models import HealthResponse, SavingsEstimateRequest, SavingsEstimateResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    hyperliquid_client = HyperliquidClient(
        info_url=settings.hyperliquid_info_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    estimator = HyperliquidSavingsEstimator(hyperliquid_client)

    app.state.hyperliquid_client = hyperliquid_client
    app.state.estimator = estimator

    try:
        yield
    finally:
        await hyperliquid_client.close()


app = FastAPI(title="Fee Savings Service", lifespan=lifespan)
static_dir = files("fee_savings_service").joinpath("static")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir.joinpath("index.html"))


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    return HealthResponse(ok=True)


@app.post("/v1/hyperliquid/savings-estimate", response_model=SavingsEstimateResponse)
async def savings_estimate(payload: SavingsEstimateRequest) -> SavingsEstimateResponse:
    try:
        return await app.state.estimator.estimate(
            address=payload.address,
            window=payload.window,
            max_fill_requests=payload.max_fill_requests or settings.default_max_fill_requests,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
