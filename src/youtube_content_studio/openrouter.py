from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from .cache import SQLiteCache
from .utils import parse_json_like, sha256_text


class OpenRouterClient:
    def __init__(self, settings: Any, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = settings.openrouter_base_url.rstrip("/")
        self.model = settings.openrouter_model

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
        }
        if self.settings.openrouter_site_url:
            headers["HTTP-Referer"] = self.settings.openrouter_site_url
        if self.settings.openrouter_app_name:
            headers["X-Title"] = self.settings.openrouter_app_name
        return headers

    def _cache_key(self, payload: dict[str, Any]) -> str:
        return sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str))

    async def chat_text(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int = 4000,
        cache_namespace: str = "llm_text",
    ) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            "max_tokens": max_tokens,
        }
        cache_key = self._cache_key(payload)
        if self.cache:
            cached = self.cache.get_json(cache_namespace, cache_key)
            if cached and isinstance(cached, dict) and "content" in cached:
                return str(cached["content"])

        content = await self._request_with_retries(payload)
        if self.cache:
            self.cache.set_json(cache_namespace, cache_key, {"content": content})
        return content

    async def chat_json(
        self,
        system: str,
        user: str,
        temperature: float | None = None,
        max_tokens: int = 4000,
        cache_namespace: str = "llm_json",
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature if temperature is not None else self.settings.llm_temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        cache_key = self._cache_key(payload)
        if self.cache:
            cached = self.cache.get_json(cache_namespace, cache_key)
            if cached is not None:
                return cached

        try:
            content = await self._request_with_retries(payload)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 400:
                payload.pop("response_format", None)
                content = await self._request_with_retries(payload)
            else:
                raise

        parsed = parse_json_like(content)
        if parsed is None:
            repaired = await self._repair_json(content)
            parsed = parse_json_like(repaired)
        if parsed is None:
            raise ValueError(f"OpenRouter returned invalid JSON: {content[:500]}")

        if self.cache:
            self.cache.set_json(cache_namespace, cache_key, parsed)
        return parsed

    async def _repair_json(self, content: str) -> str:
        repair_system = "You fix malformed JSON. Return valid JSON only."
        repair_user = f"Repair this into valid JSON only:\n\n{content}"
        return await self.chat_text(repair_system, repair_user, temperature=0.0, max_tokens=2000, cache_namespace="llm_repair")

    async def _request_with_retries(self, payload: dict[str, Any]) -> str:
        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None

        for attempt in range(1, self.settings.max_llm_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=self._headers(), json=payload)
                response.raise_for_status()
                data = response.json()
                choices = data.get("choices") or []
                if not choices:
                    raise ValueError(f"OpenRouter returned no choices: {data}")
                message = choices[0].get("message") or {}
                content = message.get("content")
                if content is None:
                    raise ValueError(f"OpenRouter response missing content: {data}")
                return str(content)
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.max_llm_retries:
                    break
                await asyncio.sleep(min(2 ** attempt, 10))

        assert last_error is not None
        raise last_error
