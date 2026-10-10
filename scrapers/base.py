"""Cliente HTTP cortés: user-agent identificable, reintentos con backoff, límite por host y robots.txt."""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

# Navegador real + contacto: algunos WAF rechazan UAs no-navegador, pero nos identificamos igualmente.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0 Safari/537.36 (+descuentos-chile; uso personal, baja frecuencia)"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9",
}
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    text: str
    elapsed_s: float
    error: str | None = None
    headers: dict = field(default_factory=dict)


class PoliteClient:
    def __init__(self, min_delay_s: float = 4.0, max_retries: int = 2, timeout_s: float = 30.0):
        self.min_delay_s = min_delay_s
        self.max_retries = max_retries
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout_s, http2=False
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _throttle(self, host: str) -> None:
        wait = self._last_hit.get(host, 0) + self.min_delay_s - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait + random.uniform(0, 1))
        self._last_hit[host] = time.monotonic()

    async def robots_allows(self, url: str) -> bool | None:
        """True/False según robots.txt; None si no se pudo leer (se trata como permitido)."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = None
            try:
                await self._throttle(parts.netloc)
                r = await self._client.get(origin + "/robots.txt")
                if r.status_code == 200 and "html" not in r.headers.get("content-type", ""):
                    rp = RobotFileParser()
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        if rp is None:
            return None
        return rp.can_fetch("*", url)

    async def get(self, url: str) -> FetchResult:
        host = urlsplit(url).netloc
        t0 = time.monotonic()
        last_err = None
        for attempt in range(self.max_retries + 1):
            await self._throttle(host)
            try:
                r = await self._client.get(url)
                if r.status_code in RETRY_STATUS and attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
                    continue
                return FetchResult(url, str(r.url), r.status_code, r.text, time.monotonic() - t0,
                                   headers=dict(r.headers))
            except httpx.HTTPError as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** (attempt + 1))
        return FetchResult(url, url, None, "", time.monotonic() - t0, error=last_err)
