"""Sync client for https://api.ytapi.dev."""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import Any

from .errors import (
    AuthError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    YTAPIError,
)
from .models import (
    TEXT_FORMATS,
    BatchJob,
    BatchSubmit,
    BatchTask,
    Channel,
    ChannelLatest,
    ChannelPlaylistsPage,
    ChannelPlaylist,
    ChannelVideo,
    ChannelVideosPage,
    DurationFilter,
    PlaylistPage,
    PlaylistVideo,
    SearchItem,
    SearchPage,
    SearchSort,
    SearchType,
    SortBy,
    Suggestions,
    TrackPolicy,
    Transcript,
    TranscriptFormat,
    UploadDate,
    VideoBasicInfo,
    VideoInfo,
)

_USER_AGENT = "ytapi-python/0.1.0 (+https://docs.ytapi.dev)"
_ENV_KEYS = ("YTAPI_API_KEY", "YTAPI_KEY")
# A free account's daily limit answers 429 with Retry-After until 00:00 UTC.
# Waiting that long inside a call would hang the caller, so it is raised.
_DAILY_LIMIT_CODE = "daily_limit_exceeded"
_ERROR_TYPES: dict[int, type[YTAPIError]] = {
    401: AuthError,
    402: InsufficientCreditsError,
    404: NotFoundError,
    429: RateLimitedError,
}


class YTAPI:
    """Synchronous YTAPI client.

    ``api_key`` falls back to the ``YTAPI_API_KEY`` environment variable,
    then ``YTAPI_KEY``.

    ``max_retries`` is the number of extra attempts after the first. They are
    used for HTTP 429, 5xx and network errors (timeouts, dropped connections),
    unless the body sets ``retryable`` to false. A 429 whose ``Retry-After`` is
    longer than ``max_retry_wait`` seconds, such as a free account's daily
    limit, is raised at once instead of waited out. ``max_retries=0`` disables
    retries. Creating a batch is never retried after a 5xx or a network error,
    since the job may already exist.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = "https://api.ytapi.dev",
        timeout: float = 30,
        max_retries: int = 2,
        backoff: float = 0.5,
        backoff_cap: float = 8,
        max_retry_wait: float = 60,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        key = api_key
        if key is None:
            key = next((os.environ[name] for name in _ENV_KEYS if os.environ.get(name)), None)
        if not key:
            raise ValueError("Pass api_key or set the YTAPI_API_KEY environment variable.")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        self.api_key = key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.backoff_cap = backoff_cap
        self.max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._monotonic = monotonic

    def get_transcript(
        self,
        video_id: str,
        *,
        format: TranscriptFormat | None = None,
        word_level: bool | None = None,
        languages: Sequence[str] | None = None,
        track_policy: TrackPolicy | None = None,
    ) -> Transcript | str:
        """Captions for one video. Text formats return the document as a string."""
        body: dict[str, Any] = {"video_id": video_id}
        if format is not None:
            body["format"] = format
        if word_level is not None:
            body["word_level"] = word_level
        if languages is not None:
            body["languages"] = list(languages)
        if track_policy is not None:
            body["track_policy"] = track_policy
        as_text = format in TEXT_FORMATS
        return self._request("POST", "/v1/transcripts", json_body=body, as_text=as_text)

    def get_basic_info(self, video_id: str) -> VideoBasicInfo:
        """Title, duration, channel and caption languages. Costs 0 credits."""
        return self._request("GET", f"/v1/videos/{_seg(video_id)}/basic-info")

    def get_video_info(self, video_id: str) -> VideoInfo:
        """Full metadata, including description, counts and chapters. 1 credit."""
        return self._request("GET", f"/v1/videos/{_seg(video_id)}/video-info")

    def get_playlist(self, playlist_id: str, *, cursor: str | None = None) -> PlaylistPage:
        """One page of a playlist. Later pages carry videos only. 1 credit per page."""
        return self._request(
            "GET", f"/v1/playlists/{_seg(playlist_id)}", query={"cursor": cursor}
        )

    def iter_playlist_videos(self, playlist_id: str) -> Iterator[PlaylistVideo]:
        """Every video in a playlist, following ``next_cursor``."""
        yield from _pages(
            lambda cursor: self.get_playlist(playlist_id, cursor=cursor),
            "videos",
        )

    def get_channel(self, channel_id: str) -> Channel:
        """Channel profile. ``channel_id`` may be ``@handle`` or ``UC...``. 1 credit."""
        return self._request("GET", f"/v1/channels/{_seg(channel_id)}")

    def get_channel_latest(self, channel_id: str) -> ChannelLatest:
        """The latest upload and a short list of recent videos. 1 credit."""
        return self._request("GET", f"/v1/channels/{_seg(channel_id)}/latest")

    def list_channel_videos(
        self,
        channel_id: str,
        *,
        cursor: str | None = None,
        sort_by: SortBy | None = None,
    ) -> ChannelVideosPage:
        """One page of uploads. 1 credit per page."""
        return self._request(
            "GET",
            f"/v1/channels/{_seg(channel_id)}/videos",
            query={"cursor": cursor, "sort_by": sort_by},
        )

    def iter_channel_videos(
        self, channel_id: str, *, sort_by: SortBy | None = None
    ) -> Iterator[ChannelVideo]:
        """Every upload, following ``next_cursor``. ``sort_by`` is sent on each page."""
        yield from _pages(
            lambda cursor: self.list_channel_videos(
                channel_id, cursor=cursor, sort_by=sort_by
            ),
            "videos",
        )

    def list_channel_playlists(
        self, channel_id: str, *, cursor: str | None = None
    ) -> ChannelPlaylistsPage:
        """One page of the channel's playlists. 1 credit per page."""
        return self._request(
            "GET",
            f"/v1/channels/{_seg(channel_id)}/playlists",
            query={"cursor": cursor},
        )

    def iter_channel_playlists(self, channel_id: str) -> Iterator[ChannelPlaylist]:
        yield from _pages(
            lambda cursor: self.list_channel_playlists(channel_id, cursor=cursor),
            "playlists",
        )

    def search(
        self,
        query: str,
        *,
        type: SearchType | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        upload_date: UploadDate | None = None,
        duration: DurationFilter | None = None,
        sort_by: SearchSort | None = None,
    ) -> SearchPage:
        """One page of search results. 1 credit per page."""
        return self._request(
            "GET",
            "/v1/search",
            query={
                "q": query,
                "type": type,
                "limit": limit,
                "cursor": cursor,
                "upload_date": upload_date,
                "duration": duration,
                "sort_by": sort_by,
            },
        )

    def iter_search(
        self,
        query: str,
        *,
        type: SearchType | None = None,
        limit: int | None = None,
        upload_date: UploadDate | None = None,
        duration: DurationFilter | None = None,
        sort_by: SearchSort | None = None,
    ) -> Iterator[SearchItem]:
        """Every search hit, following ``next_cursor``."""

        def page(cursor: str | None) -> SearchPage:
            return self.search(
                query,
                type=type,
                limit=limit,
                cursor=cursor,
                upload_date=upload_date,
                duration=duration,
                sort_by=sort_by,
            )

        yield from _pages(page, "items")

    def get_suggestions(self, query: str) -> Suggestions:
        """Autocomplete strings. Costs 0 credits."""
        return self._request("GET", "/v1/search/suggestions", query={"q": query})

    def create_batch(
        self, tasks: Sequence[BatchTask], *, concurrency: int | None = None
    ) -> BatchSubmit:
        """Start a batch of up to 100 tasks. Returns the job id; poll it with ``poll_batch``."""
        body: dict[str, Any] = {"tasks": [dict(task) for task in tasks]}
        if concurrency is not None:
            body["concurrency"] = concurrency
        # A 5xx or a dropped connection can come after the job was created, so
        # a retry could start a second batch. Only 429 (nothing was created)
        # is retried here.
        return self._request("POST", "/v1/batch", json_body=body, retry_server_errors=False)

    def get_batch(self, job_id: str) -> BatchJob:
        """Status of a batch job. Free."""
        return self._request("GET", f"/v1/batch/{_seg(job_id)}")

    def poll_batch(
        self, job_id: str, *, interval: float = 1, timeout: float = 120
    ) -> BatchJob:
        """Poll until status is ``completed`` or ``failed``, or ``timeout`` seconds pass."""
        deadline = self._monotonic() + timeout
        while True:
            job = self.get_batch(job_id)
            if job.get("status") in ("completed", "failed"):
                return job
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    f"Batch {job_id} still {job.get('status')!r} after {timeout} seconds."
                )
            self._sleep(interval)

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        as_text: bool = False,
        retry_server_errors: bool = True,
    ) -> Any:
        url = self.base_url + path
        if query:
            pairs = [(key, value) for key, value in query.items() if value is not None]
            if pairs:
                url = url + "?" + urllib.parse.urlencode(pairs)
        data = None if json_body is None else json.dumps(json_body).encode()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json, text/plain, text/vtt, text/markdown",
            "User-Agent": _USER_AGENT,
        }
        if data is not None:
            headers["Content-Type"] = "application/json"

        attempt = 0
        while True:
            request = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status = response.status
                    raw = response.read()
                    header_map = {key.lower(): value for key, value in response.headers.items()}
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read()
                header_map = {key.lower(): value for key, value in exc.headers.items()}
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
                reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
                error = YTAPIError(f"Request failed: {reason}", status=0, retryable=True)
                if attempt >= self.max_retries or not retry_server_errors:
                    raise error from exc
                self._sleep(self._backoff_delay(attempt))
                attempt += 1
                continue

            if status in (200, 202):
                if as_text:
                    return raw.decode("utf-8")
                if not raw:
                    return {}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise YTAPIError(
                        f"Expected JSON from {method} {path}, got: {raw[:200]!r}",
                        status=status,
                        retryable=False,
                    ) from exc

            error = _error_from(status, header_map, raw)
            if attempt >= self.max_retries or not _should_retry(
                error, retry_server_errors, self.max_retry_wait
            ):
                raise error
            delay = self._backoff_delay(attempt)
            if error.retry_after is not None:
                delay = max(delay, error.retry_after)
            self._sleep(delay)
            attempt += 1

    def _backoff_delay(self, attempt: int) -> float:
        return min(self.backoff_cap, self.backoff * (2**attempt))


def _seg(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _should_retry(
    error: YTAPIError, retry_server_errors: bool = True, max_retry_wait: float = 60
) -> bool:
    if error.retryable is False:
        return False
    if error.status == 429:
        if error.code == _DAILY_LIMIT_CODE:
            return False
        return error.retry_after is None or error.retry_after <= max_retry_wait
    return retry_server_errors and error.status >= 500


def _error_from(status: int, headers: Mapping[str, str], raw: bytes) -> YTAPIError:
    retry_after = _retry_after(headers.get("retry-after"))
    message = raw.decode("utf-8", "replace")
    code: str | None = None
    retryable: bool | None = None
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            code = err.get("code") if isinstance(err.get("code"), str) else None
            if isinstance(err.get("message"), str):
                message = err["message"]
            if isinstance(err.get("retryable"), bool):
                retryable = err["retryable"]
    kind = _ERROR_TYPES.get(status, ServerError if status >= 500 else YTAPIError)
    return kind(
        message, status=status, code=code, retryable=retryable, retry_after=retry_after
    )


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _pages(fetch_page: Callable[[str | None], Mapping[str, Any]], key: str) -> Iterator[Any]:
    cursor: str | None = None
    seen: set[str] = set()
    while True:
        page = fetch_page(cursor)
        items = page.get(key) or []
        yield from items
        next_cursor = page.get("next_cursor")
        # Stop on a repeated cursor rather than loop forever.
        if not page.get("has_more") or not next_cursor or next_cursor in seen:
            return
        seen.add(next_cursor)
        cursor = next_cursor
