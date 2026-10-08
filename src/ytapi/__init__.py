"""Python client for the YTAPI HTTP API. https://docs.ytapi.dev"""

from .client import YTAPI
from .errors import (
    AuthError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    YTAPIError,
)

__all__ = [
    "AuthError",
    "InsufficientCreditsError",
    "NotFoundError",
    "RateLimitedError",
    "ServerError",
    "YTAPI",
    "YTAPIError",
]
__version__ = "0.1.0"
