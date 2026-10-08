"""Errors raised by the YTAPI client.

The API returns ``{"error": {"code", "message", "retryable"}}``.
"""

from __future__ import annotations


class YTAPIError(Exception):
    """Base error. ``status`` is the HTTP status, or 0 for a network error."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        code: str | None = None,
        retryable: bool | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable
        self.retry_after = retry_after


class AuthError(YTAPIError):
    """401. The API key is missing or rejected."""


class InsufficientCreditsError(YTAPIError):
    """402. The credit balance cannot cover the call."""


class NotFoundError(YTAPIError):
    """404. ``code`` is captions_disabled, language_not_found, video_unavailable, or another not-found code."""


class RateLimitedError(YTAPIError):
    """429. ``retry_after`` is the wait the server asked for, in seconds.

    ``code`` is ``rate_limited`` for a burst over the key's rate (retried
    automatically) or ``daily_limit_exceeded`` when a free account used its
    requests for the day (raised at once; it resets at 00:00 UTC).
    """


class ServerError(YTAPIError):
    """5xx. Retried when ``retryable`` is not explicitly false."""
