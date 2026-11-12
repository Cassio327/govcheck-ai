import asyncio
import hashlib
import math
import time
from collections import OrderedDict, deque
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from govcheck.api.middleware.request_id import get_request_id


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after: int


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: int, max_keys: int) -> None:
        if min(limit, window_seconds, max_keys) < 1:
            raise ValueError("rate-limit values must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._buckets: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def check(self, key: str, *, now: float | None = None) -> RateLimitDecision:
        observed_at = time.monotonic() if now is None else now
        cutoff = observed_at - self.window_seconds
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._discard_expired_buckets(cutoff)
                if len(self._buckets) >= self.max_keys:
                    oldest_bucket = next(iter(self._buckets.values()))
                    retry_after = max(
                        1,
                        math.ceil(self.window_seconds - (observed_at - oldest_bucket[-1])),
                    )
                    return RateLimitDecision(
                        allowed=False,
                        remaining=0,
                        retry_after=retry_after,
                    )
                bucket = deque()
                self._buckets[key] = bucket
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            self._buckets.move_to_end(key)
            if len(bucket) >= self.limit:
                retry_after = max(1, math.ceil(self.window_seconds - (observed_at - bucket[0])))
                return RateLimitDecision(allowed=False, remaining=0, retry_after=retry_after)
            bucket.append(observed_at)
            return RateLimitDecision(
                allowed=True,
                remaining=max(0, self.limit - len(bucket)),
                retry_after=0,
            )

    def _discard_expired_buckets(self, cutoff: float) -> None:
        while self._buckets:
            _, oldest = next(iter(self._buckets.items()))
            while oldest and oldest[0] <= cutoff:
                oldest.popleft()
            if oldest:
                return
            self._buckets.popitem(last=False)


def _hashed_key(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _client_rate_limit_key(request: Request) -> str:
    client_host = request.client.host if request.client else "anonymous"
    return _hashed_key(f"client:{client_host}")


def _session_rate_limit_key(request: Request) -> str | None:
    session_id = (request.headers.get("X-Session-ID") or "").strip()
    return _hashed_key(f"session:{session_id}") if session_id else None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        session_limiter: SlidingWindowRateLimiter,
        client_limiter: SlidingWindowRateLimiter,
    ) -> None:
        super().__init__(app)
        self._session_limiter = session_limiter
        self._client_limiter = client_limiter

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.method == "OPTIONS" or not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_decision = await self._client_limiter.check(_client_rate_limit_key(request))
        if not client_decision.allowed:
            return self._limited_response(
                request,
                client_decision,
                limiter=self._client_limiter,
                scope="client",
            )

        session_key = _session_rate_limit_key(request)
        if session_key is None:
            decision = client_decision
            limiter = self._client_limiter
            scope = "client"
        else:
            decision = await self._session_limiter.check(session_key)
            limiter = self._session_limiter
            scope = "session"
            if not decision.allowed:
                return self._limited_response(
                    request,
                    decision,
                    limiter=limiter,
                    scope=scope,
                )

        headers = {
            "X-RateLimit-Limit": str(limiter.limit),
            "X-RateLimit-Remaining": str(decision.remaining),
            "X-RateLimit-Scope": scope,
        }
        response = await call_next(request)
        response.headers.update(headers)
        return response

    @staticmethod
    def _limited_response(
        request: Request,
        decision: RateLimitDecision,
        *,
        limiter: SlidingWindowRateLimiter,
        scope: str,
    ) -> JSONResponse:
        request_id = get_request_id(request)
        return JSONResponse(
            status_code=429,
            headers={
                "Retry-After": str(decision.retry_after),
                "X-RateLimit-Limit": str(limiter.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Scope": scope,
                "X-Request-ID": request_id,
            },
            content={
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Muitas requisições. Aguarde antes de tentar novamente.",
                    "request_id": request_id,
                }
            },
        )
