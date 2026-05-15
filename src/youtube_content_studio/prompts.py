from __future__ import annotations

from typing import Any

from .models import ContentBrief, LongFormScript, RepurposedAssets, ShortScript, VideoAnalysis, VideoCandidate
from .utils import normalize_whitespace, truncate_text


SYSTEM_PROMPT = (
    "You are an autonomous AI YouTube content studio for faceless AI-niche channels. "
    "You optimize for retention, novelty, clarity, and practical execution. "
    "When asked for JSON, return valid JSON only."
)


def analysis_prompt(video: VideoCandidate, digest: dict[str, Any], settings: dict[str, Any]) -> tuple[str, str]:
    system = SYSTEM_PROMPT
    user = f"""
Analyze this YouTube video and return a JSON object with these keys:
hook_type, hook_strength, audience, core_problem, promise, topic_angle, hook_summary,
viral_factors, retention_devices, pattern_breaks, key_claims, chapter_map, thumbnail_direction,
title_patterns, cta_style, risks, recommended_angle, transcript_summary.

Constraints:
- hook_strength is 0-100.
- viral_factors, retention_devices, pattern_breaks, key_claims, chapter_map, title_patterns, risks are arrays of short phrases.
- transcript_summary should be 2-4 sentences.
- recommended_angle should be a practical content angle for a faceless AI YouTube channel.

Video metadata:
Title: {video.title}
Channel: {video.channel}
Description: {truncate_text(normalize_whitespace(video.description), 1800)}
Views: {video.view_count}
Likes: {video.like_count}
Comments: {video.comment_count}
Duration seconds: {video.duration_seconds}
Published at: {video.published_at}
Top keywords: {", ".join(digest.get("top_keywords", []))}
Opening moments: {digest.get("opening_moments", "")}
Transcript excerpt: {truncate_text(digest.get("excerpt", ""), settings.get("analysis_excerpt_chars", 4500))}
"""
    return system, user.strip()


def brief_prompt(research_summary: dict[str, Any], analyses: list[VideoAnalysis], settings: dict[str, Any], count: int) -> tuple[str, str]:
    system = SYSTEM_PROMPT
    analysis_payload = [
        {
            "video_id": item.video_id,
            "hook_type": item.hook_type,
            "hook_strength": item.hook_strength,
            "audience": item.audience,
            "promise": item.promise,
            "topic_angle": item.topic_angle,
            "viral_factors": item.viral_factors,
            "retention_devices": item.retention_devices,
            "thumbnail_direction": item.thumbnail_direction,
            "recommended_angle": item.recommended_angle,
            "score": item.score,
        }
        for item in analyses
    ]
    user = f"""
You are planning content for an AI niche YouTube channel.

Create {count} distinct content briefs as JSON with shape:
{{"briefs": [{{"brief_id": "...", "topic": "...", "angle": "...", "why_now": "...", "audience": "...", "promise": "...", "hook_strategy": "...", "outline": ["..."], "long_form_goal": "...", "short_form_goal": "...", "thumbnail_prompt": "...", "source_video_ids": ["..."], "keywords": ["..."], "target_runtime_minutes": 8, "target_short_runtime_seconds": 45, "notes": "..."}}]}}

Rules:
- Make the briefs non-redundant.
- Each brief must be specifically usable for both a long-form video and Shorts.
- Favor angles with strong retention mechanics, novelty, and AI utility.
- Use the research summary and analyzed patterns below.

Research summary:
{research_summary}

Analyzed patterns:
{analysis_payload}
"""
    return system, user.strip()


def long_form_prompt(brief: ContentBrief, analysis_context: dict[str, Any]) -> tuple[str, str]:
    system = SYSTEM_PROMPT
    user = f"""
Write a long-form YouTube script package as JSON with shape:
{{"title_options": ["..."], "hook": "...", "intro": "...", "sections": [{{"heading": "...", "narration": "...", "visuals": "...", "retention_note": "..."}}], "cta": "...", "description": "...", "thumbnail_prompt": "...", "chapter_outline": ["..."], "retention_notes": ["..."], "production_notes": ["..."]}}

Requirements:
- Target faceless AI-channel viewers.
- Make the hook immediate and specific.
- Structure the body for retention with pattern interrupts, clear transitions, and practical value.
- Keep the narration modern, direct, and polished.
- Use 8-12 minute pacing unless the brief says otherwise.

Brief:
{brief}

Context:
{analysis_context}
"""
    return system, user.strip()


def shorts_prompt(brief: ContentBrief, long_form: LongFormScript, count: int) -> tuple[str, str]:
    system = SYSTEM_PROMPT
    user = f"""
Write {count} YouTube Shorts scripts as JSON with shape:
{{"shorts": [{{"short_id": "...", "title": "...", "hook": "...", "beats": ["..."], "visual_cues": ["..."], "on_screen_text": ["..."], "caption": "...", "hashtags": ["..."], "cta": "...", "duration_seconds": 45, "production_notes": ["..."]}}]}}

Requirements:
- Each short should feel distinct but stay on-topic with the brief.
- Prioritize strong first-line hooks, quick payoff, and a clean CTA.
- Keep each script optimized for faceless delivery.

Brief:
{brief}

Long-form script:
{long_form}
"""
    return system, user.strip()


def repurpose_prompt(brief: ContentBrief, long_form: LongFormScript, shorts: list[ShortScript]) -> tuple[str, str]:
    system = SYSTEM_PROMPT
    user = f"""
Repurpose the content into a JSON object with shape:
{{"tweets": ["..."], "linkedin_post": "...", "instagram_caption": "...", "tiktok_script": "...", "blog_outline": ["..."], "blog_article": "..."}}

Requirements:
- Tweets should be punchy and usable independently.
- LinkedIn should sound thoughtful and credible.
- Instagram caption should be visually evocative and CTA-driven.
- TikTok script should feel native to short-form video.
- Blog article should be readable, useful, and consistent with the YouTube angle.

Brief:
{brief}

Long-form script:
{long_form}

Short scripts:
{shorts}
"""
    return system, user.strip()

