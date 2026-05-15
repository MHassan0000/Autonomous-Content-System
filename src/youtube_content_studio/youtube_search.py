from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from yt_dlp import YoutubeDL

from .cache import SQLiteCache
from .models import VideoCandidate
from .utils import compute_age_days, normalize_whitespace, normalize_video_url


class YouTubeResearcher:
    def __init__(self, settings: Any, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)
        self._client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)

    async def close(self) -> None:
        await self._client.aclose()

    async def search(self, queries: list[str] | None = None) -> list[VideoCandidate]:
        queries = queries or self.settings.youtube_search_queries
        tasks = [self._search_query(query, mode) for query in queries for mode in self.settings.search_modes]
        results = await asyncio.gather(*tasks)
        flattened = [item for batch in results for item in batch]

        merged: dict[str, VideoCandidate] = {}
        for item in flattened:
            if not item.video_id:
                continue
            if item.video_id not in merged:
                merged[item.video_id] = item
            else:
                existing = merged[item.video_id]
                existing.search_queries = sorted(set(existing.search_queries + item.search_queries))
                existing.search_modes = sorted(set(existing.search_modes + item.search_modes))
                existing.search_ranks = sorted(set(existing.search_ranks + item.search_ranks))
                existing.search_signal_count += item.search_signal_count
        candidates = list(merged.values())
        candidates = sorted(candidates, key=lambda v: (v.search_signal_count, v.view_count, -v.age_days), reverse=True)
        return candidates[: self.settings.max_candidate_videos]

    async def _search_query(self, query: str, mode: str) -> list[VideoCandidate]:
        cache_key = SQLiteCache.make_key("search", query, mode, self.settings.search_results_per_query)
        if self.cache:
            cached = self.cache.get_json("youtube_search", cache_key)
            if cached:
                return [VideoCandidate(**item) for item in cached]

        url = "https://www.youtube.com/results"
        params = {"search_query": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        response = await self._client.get(url, params=params, headers=headers)
        response.raise_for_status()
        html = response.text
        items = self._parse_search_results(html, query, mode)

        if self.cache:
            self.cache.set_json("youtube_search", cache_key, [item.__dict__ for item in items], ttl_seconds=6 * 3600)
        return items

    def _parse_search_results(self, html: str, query: str, mode: str) -> list[VideoCandidate]:
        yt_initial = self._extract_yt_initial_data(html)
        candidates: list[VideoCandidate] = []

        if yt_initial:
            for rank, section in enumerate(self._walk_items(yt_initial), start=1):
                if not isinstance(section, dict):
                    continue
                renderer = section.get("videoRenderer") or section.get("richItemRenderer", {}).get("content", {}).get("videoRenderer")
                if not renderer:
                    continue
                candidate = self._renderer_to_candidate(renderer, query, mode, rank)
                if candidate.video_id:
                    candidates.append(candidate)

        if not candidates:
            # Fallback: parse watch URLs directly from the HTML
            seen: set[str] = set()
            for match in re.finditer(r'"watch\?v=([A-Za-z0-9_-]{11})"', html):
                video_id = match.group(1)
                if video_id in seen:
                    continue
                seen.add(video_id)
                candidates.append(
                    VideoCandidate(
                        video_id=video_id,
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        title=query,
                        search_queries=[query],
                        search_modes=[mode],
                        search_ranks=[len(candidates) + 1],
                        search_signal_count=1,
                        search_query=query,
                        search_mode=mode,
                    )
                )

        return candidates[: self.settings.search_results_per_query]

    def _extract_yt_initial_data(self, html: str) -> dict[str, Any] | None:
        patterns = [
            r"var ytInitialData = (\{.*?\});</script>",
            r"window\[\"ytInitialData\"\] = (\{.*?\});",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.DOTALL)
            if not match:
                continue
            raw = match.group(1)
            try:
                return json.loads(raw)
            except Exception:
                try:
                    return json.loads(self._cleanup_js_object(raw))
                except Exception:
                    continue
        return None

    def _cleanup_js_object(self, text: str) -> str:
        text = re.sub(r"([\{,]\s*)([A-Za-z0-9_]+)\s*:", r'\1"\2":', text)
        text = text.replace("undefined", "null")
        return text

    def _walk_items(self, obj: Any):
        if isinstance(obj, dict):
            yield obj
            for value in obj.values():
                yield from self._walk_items(value)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._walk_items(item)

    def _renderer_to_candidate(self, renderer: dict[str, Any], query: str, mode: str, rank: int) -> VideoCandidate:
        video_id = renderer.get("videoId", "")
        title = self._text(renderer.get("title"))
        description = self._text(renderer.get("descriptionSnippet"))
        channel = self._text(renderer.get("ownerText"))
        channel_url = self._url(renderer.get("ownerText"))
        thumbnail_url = self._thumbnail(renderer)
        published = self._text(renderer.get("publishedTimeText"))
        duration = self._duration(renderer)
        view_count = self._view_count(renderer)
        subtitle_languages = self._subtitle_languages(renderer)

        candidate = VideoCandidate(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
            title=title,
            channel=channel,
            channel_url=channel_url,
            description=description,
            published_at=published,
            upload_date=published,
            duration_seconds=duration,
            view_count=view_count,
            like_count=0,
            comment_count=0,
            tags=[],
            thumbnail_url=thumbnail_url,
            chapters=[],
            subtitle_languages=subtitle_languages,
            search_queries=[query],
            search_modes=[mode],
            search_ranks=[rank],
            search_signal_count=1,
            source_rank=rank,
            search_query=query,
            search_mode=mode,
        )
        candidate.age_days = compute_age_days(candidate.published_at)
        candidate.views_per_day = round(candidate.view_count / max(candidate.age_days, 1.0), 2)
        candidate.trend_score = 0.0
        return candidate

    def _text(self, data: Any) -> str:
        if isinstance(data, dict):
            if "simpleText" in data:
                return normalize_whitespace(str(data["simpleText"]))
            runs = data.get("runs") or []
            return normalize_whitespace("".join(run.get("text", "") for run in runs))
        if isinstance(data, list):
            return normalize_whitespace("".join(self._text(item) for item in data))
        return normalize_whitespace(str(data or ""))

    def _url(self, data: Any) -> str:
        if isinstance(data, dict):
            runs = data.get("runs") or []
            for run in runs:
                nav = run.get("navigationEndpoint", {})
                url = nav.get("commandMetadata", {}).get("webCommandMetadata", {}).get("url")
                if url:
                    return "https://www.youtube.com" + url if url.startswith("/") else url
        return ""

    def _thumbnail(self, renderer: dict[str, Any]) -> str:
        thumbs = renderer.get("thumbnail", {}).get("thumbnails") or []
        if thumbs:
            return thumbs[-1].get("url", "")
        return ""

    def _duration(self, renderer: dict[str, Any]) -> int:
        data = renderer.get("lengthText") or renderer.get("thumbnailOverlays", [])
        text = self._text(data)
        match = re.search(r"(?:(\d+):)?(\d{1,2}):(\d{2})", text)
        if match:
            if match.group(1) is not None:
                return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))
            return int(match.group(2)) * 60 + int(match.group(3))
        match = re.search(r"(\d+)\s*sec", text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 0

    def _view_count(self, renderer: dict[str, Any]) -> int:
        text = self._text(renderer.get("viewCountText"))
        match = re.search(r"([\d,.]+)\s+views", text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                return int(float(raw))
            except Exception:
                return 0
        return 0

    def _subtitle_languages(self, renderer: dict[str, Any]) -> list[str]:
        languages: list[str] = []
        for key in ("badges", "ownerBadges"):
            badges = renderer.get(key) or []
            for badge in badges:
                label = self._text(badge)
                if label and label not in languages:
                    languages.append(label)
        return languages


class SearchFallbackError(RuntimeError):
    pass


class YouTubeVideoLoader:
    def __init__(self, settings: Any, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)

    async def fetch_video_metadata(self, candidate: VideoCandidate) -> VideoCandidate:
        cache_key = SQLiteCache.make_key("video_info", candidate.video_id)
        if self.cache:
            cached = self.cache.get_json("youtube_video_info", cache_key)
            if cached:
                return VideoCandidate(**cached)

        try:
            metadata = await asyncio.wait_for(
                asyncio.to_thread(self._extract_metadata_sync, candidate.video_id),
                timeout=self.settings.video_info_timeout_seconds,
            )
        except Exception as exc:
            self.logger.debug("Video metadata fetch failed for %s: %s", candidate.video_id, exc)
            metadata = {}
        if metadata:
            candidate = self._merge(candidate, metadata)
        candidate.age_days = compute_age_days(candidate.published_at)
        candidate.views_per_day = round(candidate.view_count / max(candidate.age_days, 1.0), 2) if candidate.view_count else 0.0

        if self.cache:
            self.cache.set_json("youtube_video_info", cache_key, candidate.__dict__, ttl_seconds=24 * 3600)
        return candidate

    def _merge(self, candidate: VideoCandidate, metadata: dict[str, Any]) -> VideoCandidate:
        candidate.title = metadata.get("title") or candidate.title
        candidate.channel = metadata.get("uploader") or metadata.get("channel") or candidate.channel
        candidate.channel_url = metadata.get("uploader_url") or candidate.channel_url
        candidate.description = metadata.get("description") or candidate.description
        candidate.duration_seconds = int(metadata.get("duration") or candidate.duration_seconds or 0)
        candidate.view_count = int(metadata.get("view_count") or candidate.view_count or 0)
        candidate.like_count = int(metadata.get("like_count") or candidate.like_count or 0)
        candidate.comment_count = int(metadata.get("comment_count") or candidate.comment_count or 0)
        candidate.thumbnail_url = metadata.get("thumbnail") or candidate.thumbnail_url
        candidate.tags = metadata.get("tags") or candidate.tags
        candidate.upload_date = metadata.get("upload_date") or metadata.get("release_date") or candidate.upload_date
        candidate.published_at = candidate.published_at or metadata.get("upload_date") or metadata.get("release_date") or ""
        candidate.subtitle_languages = metadata.get("subtitles") or candidate.subtitle_languages
        candidate.chapters = metadata.get("chapters") or candidate.chapters
        return candidate

    def _extract_metadata_sync(self, video_id: str) -> dict[str, Any]:
        url = normalize_video_url(video_id)
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "extract_flat": False,
            "socket_timeout": self.settings.video_info_timeout_seconds,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return {}
        chapters = info.get("chapters") or []
        cleaned_chapters = []
        for chapter in chapters:
            cleaned_chapters.append(
                {
                    "title": chapter.get("title", ""),
                    "start_time": chapter.get("start_time", 0),
                    "end_time": chapter.get("end_time", 0),
                }
            )
        subtitles = list((info.get("subtitles") or {}).keys())
        thumbnail = info.get("thumbnail") or ""
        return {
            "id": info.get("id", ""),
            "title": info.get("title", ""),
            "uploader": info.get("uploader", ""),
            "uploader_url": info.get("uploader_url", ""),
            "description": info.get("description", ""),
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "like_count": info.get("like_count", 0),
            "comment_count": info.get("comment_count", 0),
            "thumbnail": thumbnail,
            "tags": info.get("tags", []) or [],
            "upload_date": self._format_upload_date(info.get("upload_date")),
            "release_date": info.get("release_date", ""),
            "subtitles": subtitles,
            "chapters": cleaned_chapters,
        }

    def _format_upload_date(self, value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            return value
