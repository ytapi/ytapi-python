"""Response shapes documented at https://docs.ytapi.dev.

Fields are optional in the type because pages after the first omit some of
them (a playlist page after the first carries videos only). The client
returns the JSON object as decoded; it does not drop unknown keys.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

TranscriptFormat = Literal[
    "segments",
    "word_timestamps",
    "sentences",
    "markdown",
    "text",
    "srt",
    "vtt",
    "json3",
]
TrackPolicy = Literal["manual_first", "asr_first", "exact_only"]
SearchType = Literal["video", "channel", "playlist", "shorts", "movie"]
SortBy = Literal["newest", "popular", "oldest"]
UploadDate = Literal["hour", "today", "week", "month", "year"]
DurationFilter = Literal["short", "medium", "long"]
SearchSort = Literal["relevance", "rating", "upload_date", "view_count"]
BatchTaskType = Literal["transcript", "basic_info"]
BatchStatus = Literal["pending", "processing", "completed", "failed"]

JSON_FORMATS = frozenset({"segments", "word_timestamps", "sentences", "json3"})
TEXT_FORMATS = frozenset({"markdown", "text", "srt", "vtt"})


class Thumbnail(TypedDict, total=False):
    url: str
    width: int
    height: int


class Word(TypedDict, total=False):
    word: str
    start: float
    end: float


class Segment(TypedDict, total=False):
    text: str
    start: float
    end: float
    duration: float
    words: list[Word]


class Transcript(TypedDict, total=False):
    video_id: str
    language: str
    track_kind: Literal["manual", "asr"]
    duration_seconds: float
    has_word_level: bool
    segments: list[Segment]


class CaptionLanguage(TypedDict, total=False):
    code: str
    name: str
    kind: str


class BasicChannel(TypedDict, total=False):
    id: str
    title: str
    url: str


class VideoBasicInfo(TypedDict, total=False):
    video_id: str
    title: str
    length_seconds: float
    channel: BasicChannel
    available_languages: list[CaptionLanguage]


class VideoChannel(TypedDict, total=False):
    id: str
    title: str
    url: str
    subscribers: str
    avatar_url: str


class Chapter(TypedDict, total=False):
    title: str
    start_time_seconds: float
    time_description: str


class VideoInfo(TypedDict, total=False):
    video_id: str
    title: str
    description: str
    length_seconds: float
    view_count: int
    like_count: int
    published: int
    keywords: list[str]
    channel: VideoChannel
    thumbnails: list[Thumbnail]
    available_languages: list[CaptionLanguage]
    chapters: list[Chapter]


class PlaylistVideo(TypedDict, total=False):
    video_id: str
    title: str
    index: int
    length_seconds: float
    length_text: str
    author: str


class PlaylistPage(TypedDict, total=False):
    playlist_id: str
    title: str
    video_count: int
    view_count_text: str
    author: str
    thumbnails: list[Thumbnail]
    videos: list[PlaylistVideo]
    has_more: bool
    next_cursor: str | None


class Channel(TypedDict, total=False):
    channel_id: str
    title: str
    handle: str
    description: str
    subscriber_count: int
    subscriber_count_text: str
    custom_url: str
    country: str
    video_count: int
    verified: bool
    thumbnails: list[Thumbnail]
    banners: list[Thumbnail]
    links: list[str]
    available_tabs: list[str]


class ChannelVideo(TypedDict, total=False):
    video_id: str
    title: str
    length_text: str
    view_count_text: str
    published_text: str
    thumbnails: list[Thumbnail]


class ChannelLatest(TypedDict, total=False):
    channel_id: str
    channel_title: str
    latest_video: ChannelVideo
    recent_videos: list[ChannelVideo]


class ChannelVideosPage(TypedDict, total=False):
    channel_id: str
    channel_title: str
    has_more: bool
    next_cursor: str | None
    continuation: str | None
    videos: list[ChannelVideo]


class ChannelPlaylist(TypedDict, total=False):
    playlist_id: str
    title: str
    video_count: int
    video_count_text: str
    thumbnails: list[Thumbnail]


class ChannelPlaylistsPage(TypedDict, total=False):
    playlists: list[ChannelPlaylist]
    has_more: bool
    next_cursor: str | None


class SearchItem(TypedDict, total=False):
    id: str
    type: str
    title: str
    description: str
    author: str
    channel_id: str
    length_seconds: float
    length_text: str
    view_count_text: str
    published_text: str
    thumbnails: list[Thumbnail]
    handle: str
    subscriber_count_text: str
    video_count_text: str
    badges: list[str]


class SearchPage(TypedDict, total=False):
    query: str
    type: str
    has_more: bool
    next_cursor: str | None
    items: list[SearchItem]


class Suggestions(TypedDict, total=False):
    query: str
    suggestions: list[str]


class BatchTask(TypedDict, total=False):
    id: str
    type: BatchTaskType
    video_id: str
    format: TranscriptFormat
    languages: list[str]
    track_policy: TrackPolicy
    word_level: bool


class BatchSubmit(TypedDict, total=False):
    id: str
    status: str
    total: int
    estimated_credits: int
    created_at: str


class BatchTaskError(TypedDict, total=False):
    code: str
    message: str


class BatchTaskResult(TypedDict, total=False):
    id: str
    type: str
    video_id: str
    status: int
    data: Any
    error: BatchTaskError


class BatchJob(TypedDict, total=False):
    id: str
    status: str
    total: int
    successful: int
    failed: int
    credits_deducted: int
    duration_ms: int
    results: list[BatchTaskResult]
    created_at: str
    completed_at: str | None
