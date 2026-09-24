# Fee Savings Service

A small service that estimates Hyperliquid trading fees for a wallet over a selected window.

## How it works

1. Pull the user's current Hyperliquid fee rates from `userFees`.
2. Pull the user's Hyperliquid portfolio volume windows from `portfolio`.
3. Pull recent fill data up to a configurable request limit.
4. Use exact fill fees when the fetched fills cover the full window.
5. Otherwise estimate from portfolio volume and the best available recent maker/taker mix.
6. Compare against a zero-fee target venue assumption.
7. Report the estimated savings.

## Notes

This is an estimator, not an exact historical fee ledger.

- It uses Hyperliquid current rates.
- It uses Hyperliquid portfolio volume windows.
- It uses recent fills first and falls back to `dailyUserVlm` when needed.
- It models perp volume only, because the available summary sources do not cleanly split spot maker/taker volume.

## Proposed request flow

1. Client submits a Hyperliquid address and a window.
2. Service requests `userFees`.
3. Service requests `portfolio`.
4. Service requests recent fills up to the configured request limit.
5. Service computes an exact or estimated Hyperliquid fee bill for the requested window.
6. Service returns the estimated savings against the configured zero-fee assumption.

## API

### `GET /healthz`

Basic health response.

### `POST /v1/hyperliquid/savings-estimate`

Request:

```json
{
  "address": "0x5E52363E65C99fefC0E356F0DC6c37b75bf8FC91",
  "window": "7d",
  "max_fill_requests": 2
}
```

Response:

```json
{
  "address": "0x5E52363E65C99fefC0E356F0DC6c37b75bf8FC91",
  "window": "7d",
  "estimated_hl_fees_paid": 123.45,
  "estimated_savings": 123.45,
  "fee_assumption": "Target venue: 0 maker / 0 taker",
  "estimation_mode": "exact_from_fill_fees",
  "max_fill_requests": 2,
  "fill_requests_used": 1,
  "fill_count": 847,
  "fully_covered": true
}
```

## Environment

```bash
export HYPERLIQUID_INFO_URL=https://api.hyperliquid.xyz/info
export DEFAULT_MAX_FILL_REQUESTS=1
```

## Local development

```bash
cd /Users/ungus/Documents/willy/fee-savings-service
uv sync
uv run uvicorn fee_savings_service.main:app --reload
```
