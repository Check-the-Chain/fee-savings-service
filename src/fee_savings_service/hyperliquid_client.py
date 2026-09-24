from __future__ import annotations

from typing import Any

import httpx


class HyperliquidClient:
    def __init__(self, info_url: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(timeout=timeout_seconds)
        self._info_url = info_url

    async def close(self) -> None:
        await self._client.aclose()

    async def user_fees(self, address: str) -> dict[str, Any]:
        return await self._post_info({"type": "userFees", "user": address})

    async def portfolio(self, address: str) -> list[Any]:
        payload = await self._post_info({"type": "portfolio", "user": address})
        return payload if isinstance(payload, list) else []

    async def user_fills_by_time(
        self,
        address: str,
        start_time: int,
        end_time: int,
        *,
        aggregate_by_time: bool = False,
    ) -> list[Any]:
        payload = await self._post_info(
            {
                "type": "userFillsByTime",
                "user": address,
                "startTime": start_time,
                "endTime": end_time,
                "aggregateByTime": aggregate_by_time,
            }
        )
        return payload if isinstance(payload, list) else []

    async def _post_info(self, payload: dict[str, Any]) -> Any:
        response = await self._client.post(
            self._info_url,
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        return response.json()
