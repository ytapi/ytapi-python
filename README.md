# YTAPI Python client

Python client for [YTAPI](https://ytapi.dev?utm_source=github): YouTube transcripts, video details, search, channels and playlists over one HTTP API. It works from servers and cloud functions, where fetching YouTube directly tends to get blocked.

- No dependencies beyond the standard library. Python 3.10+.
- Typed responses (`TypedDict`), typed errors, automatic retries and pagination.
- Reference: [docs.ytapi.dev](https://docs.ytapi.dev).

## Install

```bash
pip install ytapi-sdk
```

The package is `ytapi-sdk` on PyPI, and you import it as `ytapi`.

## Quickstart

Get a key at [ytapi.dev](https://ytapi.dev/app/api-keys?utm_source=github). New accounts get 200 free credits, and no card is needed.

```python
from ytapi import YTAPI

api = YTAPI()  # reads YTAPI_API_KEY (or YTAPI_KEY) from the environment
transcript = api.get_transcript("dQw4w9WgXcQ")
for segment in transcript["segments"][:3]:
    print(segment["start"], segment["text"])
```

By default you get the captions in the video's own language, as timed segments. A successful request uses 1 credit, and errors are free.

## Examples

```python
# Other formats. markdown, text, srt and vtt come back as a string.
srt = api.get_transcript("dQw4w9WgXcQ", format="srt")
spanish = api.get_transcript("dQw4w9WgXcQ", format="text", languages=["es", "*"])
words = api.get_transcript("dQw4w9WgXcQ", format="word_timestamps", word_level=True)

# Free: title, length, channel and the caption languages a video has.
basic = api.get_basic_info("dQw4w9WgXcQ")
# 1 credit: description, counts, chapters and more.
info = api.get_video_info("dQw4w9WgXcQ")

# Channels take an @handle, a channel ID (UC...) or a URL.
channel = api.get_channel("@3blue1brown")
for video in api.iter_channel_videos("@3blue1brown", sort_by="popular"):
    print(video["video_id"], video["title"])

# Playlists, page by page or as an iterator.
for video in api.iter_playlist_videos("PLZHQObOWTQDNU6R1_67000Dx_ZCJB-3pi"):
    print(video["video_id"], video["length_text"])

# Search: type is video, channel, playlist, shorts or movie.
page = api.search("rust async", type="video", upload_date="month", limit=10)
for hit in page["items"]:
    print(hit["title"])

# Search suggestions are free.
print(api.get_suggestions("nextjs")["suggestions"])

# Batch: up to 100 transcript or basic_info tasks per job.
job = api.create_batch(
    [
        {"id": "a", "type": "transcript", "video_id": "dQw4w9WgXcQ", "format": "text"},
        {"id": "b", "type": "basic_info", "video_id": "jNQXAC9IVRw"},
    ]
)
done = api.poll_batch(job["id"], timeout=120)
print(done["successful"], done["credits_deducted"])
```

The iterators (`iter_playlist_videos`, `iter_channel_videos`, `iter_channel_playlists`, `iter_search`) follow `next_cursor` for you. Each page is a request and uses a credit. In a batch, each successful task uses 1 credit and failed tasks are free.

## Errors

```python
from ytapi import InsufficientCreditsError, NotFoundError, RateLimitedError, YTAPIError

try:
    api.get_transcript("xxxxxxxxxxx")
except NotFoundError as exc:
    print(exc.code)  # captions_disabled, language_not_found, video_unavailable, ...
except RateLimitedError as exc:
    print(exc.code, exc.retry_after)  # rate_limited or daily_limit_exceeded
except InsufficientCreditsError:
    print("Out of credits: https://ytapi.dev/#pricing")
except YTAPIError as exc:
    print(exc.status, exc.code, exc)  # status 0 means a network error
```

| Status | Exception |
| --- | --- |
| 401 | `AuthError` |
| 402 | `InsufficientCreditsError` |
| 404 | `NotFoundError` |
| 429 | `RateLimitedError` |
| 5xx | `ServerError` |
| network error | `YTAPIError` with `status` 0 |
| other | `YTAPIError` |

## Retries

The client retries a 429, a 5xx or a network error up to `max_retries` times (default 2). It backs off from 0.5 seconds, doubling up to 8, and waits longer when the server sends `Retry-After`. One case is not retried:

- **A 429 that asks for a long wait.** The cutoff is `max_retry_wait`, default 60 seconds. This includes a free account's daily limit (`daily_limit_exceeded`), which lasts until 00:00 UTC. The client raises these right away instead of hanging your program.

`create_batch` sends an `Idempotency-Key` header (a new UUID per call, or pass `idempotency_key=`), so a retried submit returns the job it already created instead of starting and billing a second one. Pass your own key, such as an order ID, to make retrying the whole call safe as well.

Use `YTAPI(max_retries=0)` to turn retries off.

## Releases

Each GitHub release publishes the matching version to [PyPI](https://pypi.org/project/ytapi-sdk/) through trusted publishing. The release tag must match the version in `pyproject.toml`, such as `v0.1.0`.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

The tests mock HTTP and need no network or API key.

## License

MIT
