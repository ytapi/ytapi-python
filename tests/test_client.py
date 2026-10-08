"""Mocked HTTP tests. No network, no API keys."""

from __future__ import annotations

import json
import os
import unittest
import urllib.error
import urllib.request
from unittest import mock

from ytapi import (
    AuthError,
    InsufficientCreditsError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    YTAPI,
    YTAPIError,
)


class Response:
    def __init__(self, status: int, body: bytes, headers: dict[str, str] | None = None):
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {"Content-Type": "application/json"}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def close(self) -> None:
        return None


def json_body(payload: object, status: int = 200) -> Response:
    return Response(status, json.dumps(payload).encode())


def error(status: int, code: str, message: str, retryable: bool | None = None, headers=None):
    err: dict[str, object] = {"code": code, "message": message}
    if retryable is not None:
        err["retryable"] = retryable
    response = json_body({"error": err}, status)
    if headers:
        response.headers.update(headers)
    return urllib.error.HTTPError("https://api.ytapi.dev", status, message, response.headers, response)


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.slept: list[float] = []
        self.now = 0.0

    def client(self, **kwargs: object) -> YTAPI:
        return YTAPI(
            "test-key",
            max_retries=kwargs.pop("max_retries", 2),  # type: ignore[arg-type]
            sleep=self.slept.append,
            monotonic=lambda: self.now,
            **kwargs,  # type: ignore[arg-type]
        )

    def test_requires_a_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("YTAPI_KEY", None)
            with self.assertRaises(ValueError):
                YTAPI()

    def test_reads_ytapi_key_from_the_environment(self) -> None:
        with mock.patch.dict(os.environ, {"YTAPI_KEY": "from-env"}, clear=True):
            client = YTAPI()
        self.assertEqual(client.api_key, "from-env")

    def test_prefers_ytapi_api_key(self) -> None:
        env = {"YTAPI_API_KEY": "preferred", "YTAPI_KEY": "fallback"}
        with mock.patch.dict(os.environ, env, clear=True):
            client = YTAPI()
        self.assertEqual(client.api_key, "preferred")

    def test_transcript_posts_every_option_and_returns_json(self) -> None:
        captured = {}

        def urlopen(request, timeout=None):
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["body"] = json.loads(request.data)
            captured["auth"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return json_body(
                {
                    "video_id": "dQw4w9WgXcQ",
                    "language": "en",
                    "track_kind": "asr",
                    "has_word_level": True,
                    "segments": [{"text": "hello", "start": 0, "end": 1, "words": []}],
                }
            )

        client = self.client(timeout=12)
        with mock.patch.object(urllib.request, "urlopen", urlopen):
            transcript = client.get_transcript(
                "dQw4w9WgXcQ",
                format="segments",
                word_level=True,
                languages=["es", "*"],
                track_policy="asr_first",
            )
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://api.ytapi.dev/v1/transcripts")
        self.assertEqual(captured["auth"], "Bearer test-key")
        self.assertEqual(captured["timeout"], 12)
        self.assertEqual(
            captured["body"],
            {
                "video_id": "dQw4w9WgXcQ",
                "format": "segments",
                "word_level": True,
                "languages": ["es", "*"],
                "track_policy": "asr_first",
            },
        )
        self.assertEqual(transcript["language"], "en")

    def test_text_formats_return_the_document(self) -> None:
        def urlopen(request, timeout=None):
            return Response(200, b"WEBVTT\n\nhello\n", {"Content-Type": "text/vtt"})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            text = self.client().get_transcript("dQw4w9WgXcQ", format="vtt")
        self.assertEqual(text, "WEBVTT\n\nhello\n")

    def test_srt_is_returned_as_text_even_when_the_type_is_text_plain(self) -> None:
        def urlopen(request, timeout=None):
            return Response(200, b"1\n00:00:00,000 --> 00:00:01,000\nhi\n", {"Content-Type": "text/plain"})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            text = self.client().get_transcript("abc", format="srt")
        self.assertTrue(text.startswith("1\n"))

    def test_each_read_endpoint_uses_the_documented_path(self) -> None:
        seen: list[tuple[str, str]] = []

        def urlopen(request, timeout=None):
            seen.append((request.get_method(), request.full_url))
            return json_body({"ok": True, "videos": [], "items": [], "suggestions": []})

        client = self.client()
        calls = [
            lambda: client.get_basic_info("kCc8FmEb1nY"),
            lambda: client.get_video_info("kCc8FmEb1nY"),
            lambda: client.get_playlist("PL123", cursor="c1"),
            lambda: client.get_channel("@MrBeast"),
            lambda: client.get_channel_latest("@MrBeast"),
            lambda: client.list_channel_videos("@MrBeast", sort_by="popular", cursor="v1"),
            lambda: client.list_channel_playlists("UCabcdef", cursor="p1"),
            lambda: client.search(
                "agents",
                type="video",
                limit=10,
                cursor="s1",
                upload_date="month",
                duration="short",
                sort_by="view_count",
            ),
            lambda: client.get_suggestions("next"),
            lambda: client.get_batch("batch_1"),
        ]
        with mock.patch.object(urllib.request, "urlopen", urlopen):
            for call in calls:
                call()

        paths = [url.split("?", 1)[0] for _, url in seen]
        self.assertEqual(
            paths,
            [
                "https://api.ytapi.dev/v1/videos/kCc8FmEb1nY/basic-info",
                "https://api.ytapi.dev/v1/videos/kCc8FmEb1nY/video-info",
                "https://api.ytapi.dev/v1/playlists/PL123",
                "https://api.ytapi.dev/v1/channels/%40MrBeast",
                "https://api.ytapi.dev/v1/channels/%40MrBeast/latest",
                "https://api.ytapi.dev/v1/channels/%40MrBeast/videos",
                "https://api.ytapi.dev/v1/channels/UCabcdef/playlists",
                "https://api.ytapi.dev/v1/search",
                "https://api.ytapi.dev/v1/search/suggestions",
                "https://api.ytapi.dev/v1/batch/batch_1",
            ],
        )
        playlist_query = seen[2][1].split("?", 1)[1]
        self.assertIn("cursor=c1", playlist_query)
        video_query = seen[5][1].split("?", 1)[1]
        self.assertIn("sort_by=popular", video_query)
        self.assertIn("cursor=v1", video_query)
        search_query = seen[7][1].split("?", 1)[1]
        for part in (
            "q=agents",
            "type=video",
            "limit=10",
            "cursor=s1",
            "upload_date=month",
            "duration=short",
            "sort_by=view_count",
        ):
            self.assertIn(part, search_query)
        self.assertTrue(all(method == "GET" for method, _ in seen))

    def test_batch_create_accepts_202_and_sends_concurrency(self) -> None:
        captured = {}

        def urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data)
            return json_body(
                {"id": "batch_1", "status": "pending", "total": 1, "estimated_credits": 1},
                status=202,
            )

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            job = self.client().create_batch(
                [{"id": "t1", "type": "transcript", "video_id": "dQw4w9WgXcQ", "format": "srt"}],
                concurrency=10,
            )
        self.assertEqual(job["id"], "batch_1")
        self.assertEqual(captured["body"]["concurrency"], 10)
        self.assertEqual(captured["body"]["tasks"][0]["format"], "srt")

    def test_typed_errors_are_not_retried(self) -> None:
        cases = [
            (401, "unauthorized", AuthError),
            (402, "insufficient_credits", InsufficientCreditsError),
            (404, "captions_disabled", NotFoundError),
            (400, "invalid_request", YTAPIError),
            (403, "region_blocked", YTAPIError),
        ]
        for status, code, kind in cases:
            calls = {"n": 0}

            def urlopen(request, timeout=None, status=status, code=code):
                calls["n"] += 1
                raise error(status, code, code)

            with mock.patch.object(urllib.request, "urlopen", urlopen):
                with self.assertRaises(kind) as raised:
                    self.client().get_basic_info("abc")
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(raised.exception.status, status)
            self.assertEqual(calls["n"], 1)

    def test_429_retries_then_raises_with_retry_after(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise error(
                429,
                "rate_limited",
                "slow down",
                headers={"Retry-After": "3"},
            )

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(RateLimitedError) as raised:
                self.client().get_basic_info("abc")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(raised.exception.retry_after, 3)
        self.assertEqual(self.slept, [3, 3])

    def test_5xx_stops_when_retryable_is_false(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise error(503, "upstream_error", "no", retryable=False)

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(ServerError):
                self.client().get_basic_info("abc")
        self.assertEqual(calls["n"], 1)
        self.assertEqual(self.slept, [])

    def test_5xx_retries_until_success(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise error(500, "upstream_error", "later", retryable=True)
            return json_body({"title": "ok"})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            info = self.client().get_basic_info("abc")
        self.assertEqual(info["title"], "ok")
        self.assertEqual(self.slept, [0.5, 1.0])

    def test_retries_can_be_switched_off(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise error(500, "upstream_error", "later", retryable=True)

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(ServerError):
                self.client(max_retries=0).get_basic_info("abc")
        self.assertEqual(calls["n"], 1)

    def test_network_errors_are_retried_then_raised(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.URLError("connection refused")
            raise TimeoutError("timed out")

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(YTAPIError) as raised:
                self.client().get_basic_info("abc")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(raised.exception.status, 0)
        self.assertTrue(raised.exception.retryable)
        self.assertEqual(self.slept, [0.5, 1.0])

    def test_network_error_then_success(self) -> None:
        responses = [ConnectionResetError("reset"), json_body({"video_id": "abc"})]

        def urlopen(request, timeout=None):
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            self.assertEqual(self.client().get_basic_info("abc"), {"video_id": "abc"})

    def test_batch_create_is_not_retried_after_a_network_error(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise TimeoutError("timed out")

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(YTAPIError):
                self.client().create_batch([{"type": "transcript", "video_id": "abc"}])
        self.assertEqual(calls["n"], 1)

    def test_daily_limit_is_raised_without_waiting(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise error(
                429,
                "daily_limit_exceeded",
                "free accounts can make 100 requests a day",
                retryable=True,
                headers={"Retry-After": "43200"},
            )

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(RateLimitedError) as raised:
                self.client().get_basic_info("abc")
        self.assertEqual(calls["n"], 1)
        self.assertEqual(self.slept, [])
        self.assertEqual(raised.exception.code, "daily_limit_exceeded")
        self.assertEqual(raised.exception.retry_after, 43200)

    def test_429_with_a_long_retry_after_is_raised(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            raise error(429, "rate_limited", "slow down", headers={"Retry-After": "120"})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(RateLimitedError):
                self.client().get_basic_info("abc")
        self.assertEqual(calls["n"], 1)
        self.assertEqual(self.slept, [])

    def test_non_json_success_body_raises_a_clear_error(self) -> None:
        def urlopen(request, timeout=None):
            return Response(200, b"<html>proxy page</html>", {"Content-Type": "text/html"})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(YTAPIError) as raised:
                self.client().get_basic_info("abc")
        self.assertIn("Expected JSON", str(raised.exception))

    def test_iterator_stops_on_a_repeated_cursor(self) -> None:
        calls = {"n": 0}

        def urlopen(request, timeout=None):
            calls["n"] += 1
            return json_body({"has_more": True, "next_cursor": "same", "videos": [{"video_id": "a"}]})

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            videos = list(self.client().iter_playlist_videos("PL1"))
        self.assertEqual(calls["n"], 2)
        self.assertEqual(len(videos), 2)

    def test_playlist_iterator_follows_the_cursor_and_stops(self) -> None:
        pages = [
            json_body(
                {
                    "title": "Demo",
                    "has_more": True,
                    "next_cursor": "page-2",
                    "videos": [{"video_id": "aaaaaaaaaaa", "title": "one"}],
                }
            ),
            json_body(
                {
                    "has_more": False,
                    "next_cursor": None,
                    "videos": [{"video_id": "bbbbbbbbbbb", "title": "two"}],
                }
            ),
        ]
        seen: list[str] = []

        def urlopen(request, timeout=None):
            seen.append(request.full_url)
            return pages.pop(0)

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            videos = list(self.client().iter_playlist_videos("PLdemo"))
        self.assertEqual([video["video_id"] for video in videos], ["aaaaaaaaaaa", "bbbbbbbbbbb"])
        self.assertNotIn("cursor", seen[0])
        self.assertIn("cursor=page-2", seen[1])

    def test_search_and_channel_iterators_use_item_keys(self) -> None:
        def urlopen(request, timeout=None):
            if request.full_url.startswith("https://api.ytapi.dev/v1/search?"):
                return json_body(
                    {"has_more": False, "items": [{"id": "vid", "type": "video", "title": "t"}]}
                )
            return json_body(
                {
                    "has_more": False,
                    "videos": [{"video_id": "vid", "title": "upload"}],
                    "playlists": [{"playlist_id": "PLx", "title": "list"}],
                }
            )

        with mock.patch.object(urllib.request, "urlopen", urlopen):
            client = self.client()
            hits = list(client.iter_search("q", type="playlist"))
            uploads = list(client.iter_channel_videos("@c", sort_by="oldest"))
            lists = list(client.iter_channel_playlists("@c"))
        self.assertEqual(hits[0]["id"], "vid")
        self.assertEqual(uploads[0]["title"], "upload")
        self.assertEqual(lists[0]["playlist_id"], "PLx")

    def test_poll_batch_returns_when_the_job_finishes(self) -> None:
        statuses = ["pending", "processing", "completed"]

        def urlopen(request, timeout=None):
            status = statuses.pop(0)
            return json_body({"id": "batch_1", "status": status, "successful": 1, "total": 1})

        def clock() -> float:
            self.now += 1
            return self.now

        client = YTAPI("test-key", sleep=self.slept.append, monotonic=clock)
        with mock.patch.object(urllib.request, "urlopen", urlopen):
            job = client.poll_batch("batch_1", interval=1, timeout=10)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(self.slept, [1, 1])

    def test_poll_batch_times_out(self) -> None:
        def urlopen(request, timeout=None):
            return json_body({"id": "batch_1", "status": "processing"})

        def clock() -> float:
            self.now += 5
            return self.now

        client = YTAPI("test-key", sleep=self.slept.append, monotonic=clock)
        with mock.patch.object(urllib.request, "urlopen", urlopen):
            with self.assertRaises(TimeoutError):
                client.poll_batch("batch_1", interval=1, timeout=3)


    def test_batch_create_retries_429_but_not_5xx(self) -> None:
        calls: list[int] = []

        def urlopen_503(request, timeout=None):
            calls.append(503)
            raise error(503, "upstream_error", "try again")

        with mock.patch.object(urllib.request, "urlopen", urlopen_503):
            with self.assertRaises(ServerError):
                self.client().create_batch([{"type": "transcript", "video_id": "abc"}])
        self.assertEqual(calls, [503])  # no retry: the job may already exist

        responses = [error(429, "rate_limited", "slow down"), json_body({"id": "job1", "status": "pending"}, 202)]

        def urlopen_429(request, timeout=None):
            r = responses.pop(0)
            if isinstance(r, urllib.error.HTTPError):
                raise r
            return r

        with mock.patch.object(urllib.request, "urlopen", urlopen_429):
            job = self.client().create_batch([{"type": "transcript", "video_id": "abc"}])
        self.assertEqual(job["id"], "job1")


if __name__ == "__main__":
    unittest.main()
