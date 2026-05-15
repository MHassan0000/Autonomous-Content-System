from __future__ import annotations

import asyncio
import logging
from typing import Any

from .cache import SQLiteCache
from .models import ContentBrief, ContentPackage, LongFormScript, RepurposedAssets, ShortScript, VideoAnalysis, VideoCandidate
from .openrouter import OpenRouterClient
from .prompts import brief_prompt, long_form_prompt, repurpose_prompt, shorts_prompt
from .scoring import ScoringEngine
from .utils import sha256_text


class ContentGenerator:
    def __init__(self, settings: Any, client: OpenRouterClient, cache: SQLiteCache | None = None, logger: logging.Logger | None = None):
        self.settings = settings
        self.client = client
        self.cache = cache
        self.logger = logger or logging.getLogger(__name__)
        self.scorer = ScoringEngine()

    async def generate_briefs(self, research_summary: dict[str, Any], analyses: list[VideoAnalysis], count: int | None = None) -> list[ContentBrief]:
        count = count or self.settings.ideas_per_run
        cache_key = SQLiteCache.make_key("briefs", research_summary.get("research_id", ""), [item.video_id for item in analyses], count)
        if self.cache:
            cached = self.cache.get_json("generated_briefs", cache_key)
            if cached:
                return [ContentBrief(**item) for item in cached]

        system, user = brief_prompt(research_summary, analyses, self.settings.__dict__, count)
        payload = await self.client.chat_json(system, user, temperature=0.35, max_tokens=3500, cache_namespace="briefs_json")
        briefs = [self._coerce_brief(item, analyses) for item in payload.get("briefs", []) or []]

        if self.cache:
            self.cache.set_json("generated_briefs", cache_key, [brief.__dict__ for brief in briefs], ttl_seconds=14 * 24 * 3600)
        return briefs

    async def generate_package(self, brief: ContentBrief, analyses: list[VideoAnalysis], videos: list[VideoCandidate]) -> ContentPackage:
        package = ContentPackage(brief=brief)
        package.source_analysis_ids = [item.video_id for item in analyses if item.video_id in brief.source_video_ids]

        analysis_context = {
            "brief": brief.__dict__,
            "top_analyses": [item.__dict__ for item in analyses if item.video_id in brief.source_video_ids],
        }

        long_form = await self._generate_long_form(brief, analysis_context)
        package.long_form = long_form

        shorts = await self._generate_shorts(brief, long_form, self.settings.shorts_per_idea)
        package.shorts = shorts

        repurposed = await self._generate_repurposed(brief, long_form, shorts)
        package.repurposed = repurposed

        package.brief.score, brief_breakdown = self.scorer.score_brief(brief, analyses, videos)
        package.score, package.score_breakdown = self.scorer.score_package(package)
        return package

    async def _generate_long_form(self, brief: ContentBrief, analysis_context: dict[str, Any]) -> LongFormScript:
        cache_key = SQLiteCache.make_key("long_form", brief.brief_id, brief.topic, brief.angle, brief.promise)
        if self.cache:
            cached = self.cache.get_json("generated_long_form", cache_key)
            if cached:
                return LongFormScript(**cached)

        system, user = long_form_prompt(brief, analysis_context)
        payload = await self.client.chat_json(system, user, temperature=0.35, max_tokens=4500, cache_namespace="long_form_json")
        script = self._coerce_long_form(payload)

        if self.cache:
            self.cache.set_json("generated_long_form", cache_key, script.__dict__, ttl_seconds=30 * 24 * 3600)
        return script

    async def _generate_shorts(self, brief: ContentBrief, long_form: LongFormScript, count: int) -> list[ShortScript]:
        cache_key = SQLiteCache.make_key("shorts", brief.brief_id, long_form.title_options[:2], count)
        if self.cache:
            cached = self.cache.get_json("generated_shorts", cache_key)
            if cached:
                return [ShortScript(**item) for item in cached]

        system, user = shorts_prompt(brief, long_form, count)
        payload = await self.client.chat_json(system, user, temperature=0.4, max_tokens=3000, cache_namespace="shorts_json")
        shorts = [self._coerce_short(item) for item in payload.get("shorts", []) or []]
        if self.cache:
            self.cache.set_json("generated_shorts", cache_key, [short.__dict__ for short in shorts], ttl_seconds=30 * 24 * 3600)
        return shorts

    async def _generate_repurposed(self, brief: ContentBrief, long_form: LongFormScript, shorts: list[ShortScript]) -> RepurposedAssets:
        cache_key = SQLiteCache.make_key("repurpose", brief.brief_id, long_form.title_options[:2], [short.short_id for short in shorts])
        if self.cache:
            cached = self.cache.get_json("generated_repurposed", cache_key)
            if cached:
                return RepurposedAssets(**cached)

        system, user = repurpose_prompt(brief, long_form, shorts)
        payload = await self.client.chat_json(system, user, temperature=0.4, max_tokens=4000, cache_namespace="repurpose_json")
        assets = self._coerce_repurposed(payload)

        if self.cache:
            self.cache.set_json("generated_repurposed", cache_key, assets.__dict__, ttl_seconds=30 * 24 * 3600)
        return assets

    def _coerce_brief(self, payload: dict[str, Any], analyses: list[VideoAnalysis]) -> ContentBrief:
        brief = ContentBrief(
            brief_id=str(payload.get("brief_id") or sha256_text(str(payload))[:12]),
            topic=str(payload.get("topic", "")),
            angle=str(payload.get("angle", "")),
            why_now=str(payload.get("why_now", "")),
            audience=str(payload.get("audience", "")),
            promise=str(payload.get("promise", "")),
            hook_strategy=str(payload.get("hook_strategy", "")),
            outline=list(payload.get("outline", []) or []),
            long_form_goal=str(payload.get("long_form_goal", "")),
            short_form_goal=str(payload.get("short_form_goal", "")),
            thumbnail_prompt=str(payload.get("thumbnail_prompt", "")),
            source_video_ids=list(payload.get("source_video_ids", []) or []),
            keywords=list(payload.get("keywords", []) or []),
            target_runtime_minutes=int(payload.get("target_runtime_minutes", 8) or 8),
            target_short_runtime_seconds=int(payload.get("target_short_runtime_seconds", 45) or 45),
            notes=str(payload.get("notes", "")),
        )
        if not brief.source_video_ids and analyses:
            brief.source_video_ids = [a.video_id for a in analyses[: min(3, len(analyses))]]
        return brief

    def _coerce_long_form(self, payload: dict[str, Any]) -> LongFormScript:
        return LongFormScript(
            title_options=list(payload.get("title_options", []) or []),
            hook=str(payload.get("hook", "")),
            intro=str(payload.get("intro", "")),
            sections=list(payload.get("sections", []) or []),
            cta=str(payload.get("cta", "")),
            description=str(payload.get("description", "")),
            thumbnail_prompt=str(payload.get("thumbnail_prompt", "")),
            chapter_outline=list(payload.get("chapter_outline", []) or []),
            retention_notes=list(payload.get("retention_notes", []) or []),
            production_notes=list(payload.get("production_notes", []) or []),
        )

    def _coerce_short(self, payload: dict[str, Any]) -> ShortScript:
        return ShortScript(
            short_id=str(payload.get("short_id") or sha256_text(str(payload))[:10]),
            title=str(payload.get("title", "")),
            hook=str(payload.get("hook", "")),
            beats=list(payload.get("beats", []) or []),
            visual_cues=list(payload.get("visual_cues", []) or []),
            on_screen_text=list(payload.get("on_screen_text", []) or []),
            caption=str(payload.get("caption", "")),
            hashtags=list(payload.get("hashtags", []) or []),
            cta=str(payload.get("cta", "")),
            duration_seconds=int(payload.get("duration_seconds", 45) or 45),
            production_notes=list(payload.get("production_notes", []) or []),
        )

    def _coerce_repurposed(self, payload: dict[str, Any]) -> RepurposedAssets:
        return RepurposedAssets(
            tweets=list(payload.get("tweets", []) or []),
            linkedin_post=str(payload.get("linkedin_post", "")),
            instagram_caption=str(payload.get("instagram_caption", "")),
            tiktok_script=str(payload.get("tiktok_script", "")),
            blog_outline=list(payload.get("blog_outline", []) or []),
            blog_article=str(payload.get("blog_article", "")),
        )
