from __future__ import annotations

import asyncio
import logging
from typing import Any

from .cache import SQLiteCache
from .models import TranscriptDocument, VideoAnalysis, VideoCandidate
from .openrouter import OpenRouterClient
from .prompts import analysis_prompt
from .utils import parse_json_like


class AnalysisEngine:
    def __init__(self, settings: Any, client: OpenRouterClient, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.client = client
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)

    async def analyze_many(self, videos: list[VideoCandidate], transcripts: dict[str, TranscriptDocument], research_summary: dict[str, Any]) -> list[VideoAnalysis]:
        tasks = [self.analyze(video, transcripts.get(video.video_id), research_summary) for video in videos]
        return await asyncio.gather(*tasks)

    async def analyze(self, video: VideoCandidate, transcript: TranscriptDocument | None, research_summary: dict[str, Any]) -> VideoAnalysis:
        transcript = transcript or TranscriptDocument(video_id=video.video_id)
        cache_key = SQLiteCache.make_key("analysis", video.video_id, transcript.source, transcript.word_count, video.view_count, video.like_count)
        if self.cache:
            cached = self.cache.get_json("youtube_analysis", cache_key)
            if cached:
                return VideoAnalysis(**cached)

        digest = {
            "title": video.title,
            "excerpt": transcript.excerpt,
            "opening_moments": " ".join(seg.get("text", "") for seg in transcript.segments[:5]),
            "top_keywords": [],
        }
        system, user = analysis_prompt(video, digest, self.settings.__dict__)
        payload = await self.client.chat_json(system, user, temperature=0.2, max_tokens=2500, cache_namespace="analysis_json")

        analysis = self._coerce_analysis(video, transcript, payload)
        if self.cache:
            self.cache.set_json("youtube_analysis", cache_key, analysis.__dict__, ttl_seconds=14 * 24 * 3600)
        return analysis

    def _coerce_analysis(self, video: VideoCandidate, transcript: TranscriptDocument, payload: dict[str, Any]) -> VideoAnalysis:
        analysis = VideoAnalysis(
            video_id=video.video_id,
            hook_type=str(payload.get("hook_type", "")),
            hook_strength=float(payload.get("hook_strength", 0) or 0),
            audience=str(payload.get("audience", "")),
            core_problem=str(payload.get("core_problem", "")),
            promise=str(payload.get("promise", "")),
            topic_angle=str(payload.get("topic_angle", "")),
            hook_summary=str(payload.get("hook_summary", "")),
            viral_factors=list(payload.get("viral_factors", []) or []),
            retention_devices=list(payload.get("retention_devices", []) or []),
            pattern_breaks=list(payload.get("pattern_breaks", []) or []),
            key_claims=list(payload.get("key_claims", []) or []),
            chapter_map=list(payload.get("chapter_map", []) or []),
            thumbnail_direction=str(payload.get("thumbnail_direction", "")),
            title_patterns=list(payload.get("title_patterns", []) or []),
            cta_style=str(payload.get("cta_style", "")),
            risks=list(payload.get("risks", []) or []),
            recommended_angle=str(payload.get("recommended_angle", "")),
            transcript_summary=str(payload.get("transcript_summary", "")),
            raw=payload,
        )
        if not analysis.transcript_summary:
            analysis.transcript_summary = transcript.excerpt
        return analysis
