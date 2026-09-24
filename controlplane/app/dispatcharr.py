from __future__ import annotations

from typing import Any

import httpx


class DispatcharrClient:
    def __init__(self, base_url: str, api_key: str, plugin_key: str):
        self.base_url = base_url.rstrip("/")
        self.plugin_key = plugin_key
        self._api_key = api_key

    async def _post(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/api/plugins/plugins/{self.plugin_key}/run/"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0)
        ) as client:
            response = await client.post(
                url,
                headers={"X-API-Key": self._api_key},
                json={"action": action, "params": params},
            )
            if response.status_code == 403:
                raise PermissionError(
                    "Dispatcharr rejected the request. The VOD plugin may be disabled or the API key lacks access."
                )
            if response.status_code == 404:
                raise RuntimeError("Dispatcharr VOD Catalog Manager plugin endpoint was not found")
            response.raise_for_status()
            body = response.json()
            return body.get("result", body)

    async def _get_plugins(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/plugins/plugins/"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0)
        ) as client:
            response = await client.get(
                url,
                headers={"X-API-Key": self._api_key},
            )
            if response.status_code == 401:
                raise PermissionError("Dispatcharr API key is invalid")
            response.raise_for_status()
            return response.json()

