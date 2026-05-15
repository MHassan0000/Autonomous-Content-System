from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from youtube_transcript_api import YouTubeTranscriptApi

from .cache import SQLiteCache
from .models import TranscriptDocument, VideoCandidate
from .utils import build_transcript_digest, extract_video_id, normalize_whitespace, sha256_text, truncate_text


class TranscriptExtractor:
    def __init__(self, settings: Any, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)

    async def extract(self, video: VideoCandidate) -> TranscriptDocument:
        cache_key = SQLiteCache.make_key("transcript", video.video_id, self.settings.transcript_language, self.settings.transcript_backend)
        if self.cache:
            cached = self.cache.get_json("youtube_transcript", cache_key)
            if cached:
                return TranscriptDocument(**cached)

        try:
            transcript = await asyncio.wait_for(asyncio.to_thread(self._extract_sync, video), timeout=self.settings.transcript_timeout_seconds)
        except Exception as exc:
            self.logger.debug("Transcript extraction failed for %s: %s", video.video_id, exc)
            transcript = TranscriptDocument(
                video_id=video.video_id,
                language=self.settings.transcript_language,
                source="metadata_fallback",
                segments=[],
                text=normalize_whitespace(f"{video.title} {video.description}"),
                word_count=len(normalize_whitespace(f"{video.title} {video.description}").split()),
                excerpt=truncate_text(normalize_whitespace(f"{video.title} {video.description}"), self.settings.transcript_excerpt_chars),
            )
        if self.cache:
            self.cache.set_json("youtube_transcript", cache_key, transcript.__dict__, ttl_seconds=7 * 24 * 3600)
        return transcript

    def _extract_sync(self, video: VideoCandidate) -> TranscriptDocument:
        video_id = extract_video_id(video.video_id or video.url)
        segments: list[dict[str, Any]] = []
        source = "metadata"

        try:
            segments = self._fetch_with_youtube_transcript_api(video_id)
            source = "youtube_transcript_api"
        except Exception as api_error:
            self.logger.debug("Transcript API failed for %s: %s", video_id, api_error)
            if self.settings.transcript_backend in {"auto", "yt-dlp"}:
                segments = self._from_yt_dlp(video_id)
                source = "yt_dlp"

        text = normalize_whitespace(" ".join(segment.get("text", "") for segment in segments))
        if not text:
            text = normalize_whitespace(f"{video.title} {video.description}")
            source = "metadata_fallback"

        word_count = len(text.split())
        digest = build_transcript_digest(video.title, text, segments, excerpt_chars=self.settings.transcript_excerpt_chars)
        return TranscriptDocument(
            video_id=video.video_id,
            language=self.settings.transcript_language,
            source=source,
            segments=segments,
            text=text,
            word_count=word_count,
            excerpt=digest.get("excerpt", truncate_text(text, self.settings.transcript_excerpt_chars)),
        )

    def _fetch_with_youtube_transcript_api(self, video_id: str) -> list[dict[str, Any]]:
        # Newer versions may expose fetch() on an instance; older versions use class methods.
        try_methods = []
        instance = YouTubeTranscriptApi()
        if hasattr(instance, "fetch"):
            try_methods.append(lambda: instance.fetch(video_id, languages=[self.settings.transcript_language]))
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            try_methods.append(lambda: YouTubeTranscriptApi.get_transcript(video_id, languages=[self.settings.transcript_language]))
        if hasattr(YouTubeTranscriptApi, "list_transcripts"):
            def _list_method():
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript = transcript_list.find_transcript([self.settings.transcript_language])
                return transcript.fetch()

            try_methods.append(_list_method)

            def _fallback_any_language():
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                for transcript in transcript_list:
                    try:
                        return transcript.fetch()
                    except Exception:
                        if getattr(transcript, "is_translatable", False):
                            try:
                                return transcript.translate(self.settings.transcript_language).fetch()
                            except Exception:
                                continue
                        continue
                raise RuntimeError("No usable transcript available")

            try_methods.append(_fallback_any_language)

        last_error: Exception | None = None
        for method in try_methods:
            try:
                raw = method()
                return self._normalize_segments(raw)
            except Exception as exc:
                last_error = exc
                continue

        if last_error:
            raise last_error
        raise RuntimeError("No transcript API method available")

    def _normalize_segments(self, raw: Any) -> list[dict[str, Any]]:
        segments: list[dict[str, Any]] = []
        for item in raw or []:
            if isinstance(item, dict):
                segments.append({
                    "start": float(item.get("start", 0.0) or 0.0),
                    "duration": float(item.get("duration", 0.0) or 0.0),
                    "text": str(item.get("text", "") or ""),
                })
            else:
                segments.append({
                    "start": float(getattr(item, "start", 0.0) or 0.0),
                    "duration": float(getattr(item, "duration", 0.0) or 0.0),
                    "text": str(getattr(item, "text", "") or ""),
                })
        return segments

    def _from_yt_dlp(self, video_id: str) -> list[dict[str, Any]]:
        try:
            from yt_dlp import YoutubeDL
        except Exception:
            return []

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": [self.settings.transcript_language],
            "noplaylist": True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        subtitles = info.get("subtitles") or info.get("automatic_captions") or {}
        lang_tracks = subtitles.get(self.settings.transcript_language) or []
        if not lang_tracks and subtitles:
            lang_tracks = next(iter(subtitles.values()), [])
        if not lang_tracks:
            return []

        chosen = self._choose_caption_track(lang_tracks)
        if not chosen:
            return []

        url = chosen.get("url")
        if not url:
            return []

        text = self._download_caption_text(url)
        if not text:
            return []
        return self._parse_caption_text(text, chosen.get("ext", ""))

    def _choose_caption_track(self, tracks: list[dict[str, Any]]) -> dict[str, Any] | None:
        preferred_exts = ["json3", "srv3", "vtt", "ttml"]
        for ext in preferred_exts:
            for track in tracks:
                if str(track.get("ext", "")).lower() == ext and track.get("url"):
                    return track
        for track in tracks:
            if track.get("url"):
                return track
        return None

    def _download_caption_text(self, url: str) -> str:
        try:
            with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as exc:
            self.logger.debug("Caption download failed for %s: %s", url, exc)
            return ""

    def _parse_caption_text(self, text: str, ext: str) -> list[dict[str, Any]]:
        ext = (ext or "").lower()
        if ext == "json3" or text.lstrip().startswith("{"):
            return self._parse_json3(text)
        return self._parse_vtt(text)

    def _parse_json3(self, text: str) -> list[dict[str, Any]]:
        try:
            data = json.loads(text)
        except Exception:
            return []
        segments: list[dict[str, Any]] = []
        for event in data.get("events", []):
            segs = event.get("segs", []) or []
            parts = []
            for seg in segs:
                piece = seg.get("utf8", "")
                if piece:
                    parts.append(piece)
            sentence = "".join(parts).strip()
            if not sentence:
                continue
            start = float(event.get("tStartMs", 0) or 0) / 1000.0
            duration = float(event.get("dDurationMs", 0) or 0) / 1000.0
            segments.append({"start": start, "duration": duration, "text": sentence})
        return segments

    def _parse_vtt(self, text: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in text.splitlines()]
        segments: list[dict[str, Any]] = []
        buffer: list[str] = []
        start = 0.0
        duration = 0.0
        in_block = False
        for line in lines:
            if not line or line.startswith("WEBVTT"):
                continue
            if "-->" in line:
                if buffer:
                    segments.append({"start": start, "duration": duration, "text": " ".join(buffer).strip()})
                    buffer = []
                in_block = True
                start_text, end_text = [part.strip() for part in line.split("-->", 1)]
                start = self._vtt_time_to_seconds(start_text)
                end = self._vtt_time_to_seconds(end_text.split(" ")[0])
                duration = max(end - start, 0.0)
                continue
            if line.isdigit() and not in_block:
                continue
            if in_block:
                if line:
                    buffer.append(line)
        if buffer:
            segments.append({"start": start, "duration": duration, "text": " ".join(buffer).strip()})
        return [segment for segment in segments if segment["text"]]

    def _vtt_time_to_seconds(self, value: str) -> float:
        parts = value.split(":")
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return float(hours) * 3600 + float(minutes) * 60 + float(seconds.replace(",", "."))
            if len(parts) == 2:
                minutes, seconds = parts
                return float(minutes) * 60 + float(seconds.replace(",", "."))
        except Exception:
            pass
        return 0.0
