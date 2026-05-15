from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TranscriptDocument:
    video_id: str = ""
    language: str = ""
    source: str = ""
    segments: List[Dict[str, Any]] = field(default_factory=list)
    text: str = ""
    word_count: int = 0
    excerpt: str = ""


@dataclass
class VideoCandidate:
    video_id: str = ""
    url: str = ""
    title: str = ""
    channel: str = ""
    channel_url: str = ""
    description: str = ""
    published_at: str = ""
    upload_date: str = ""
    duration_seconds: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    tags: List[str] = field(default_factory=list)
    thumbnail_url: str = ""
    chapters: List[Dict[str, Any]] = field(default_factory=list)
    subtitle_languages: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    search_modes: List[str] = field(default_factory=list)
    search_ranks: List[int] = field(default_factory=list)
    search_signal_count: int = 0
    source_rank: int = 0
    search_query: str = ""
    search_mode: str = ""
    age_days: float = 0.0
    views_per_day: float = 0.0
    trend_score: float = 0.0
    transcript_text: str = ""
    transcript_segments: List[Dict[str, Any]] = field(default_factory=list)
    transcript_source: str = ""
    analysis: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoAnalysis:
    video_id: str = ""
    hook_type: str = ""
    hook_strength: float = 0.0
    audience: str = ""
    core_problem: str = ""
    promise: str = ""
    topic_angle: str = ""
    hook_summary: str = ""
    viral_factors: List[str] = field(default_factory=list)
    retention_devices: List[str] = field(default_factory=list)
    pattern_breaks: List[str] = field(default_factory=list)
    key_claims: List[str] = field(default_factory=list)
    chapter_map: List[str] = field(default_factory=list)
    thumbnail_direction: str = ""
    title_patterns: List[str] = field(default_factory=list)
    cta_style: str = ""
    risks: List[str] = field(default_factory=list)
    recommended_angle: str = ""
    transcript_summary: str = ""
    score: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentBrief:
    brief_id: str = ""
    topic: str = ""
    angle: str = ""
    why_now: str = ""
    audience: str = ""
    promise: str = ""
    hook_strategy: str = ""
    outline: List[str] = field(default_factory=list)
    long_form_goal: str = ""
    short_form_goal: str = ""
    thumbnail_prompt: str = ""
    source_video_ids: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    score: float = 0.0
    target_runtime_minutes: int = 0
    target_short_runtime_seconds: int = 0
    notes: str = ""


@dataclass
class LongFormScript:
    title_options: List[str] = field(default_factory=list)
    hook: str = ""
    intro: str = ""
    sections: List[Dict[str, Any]] = field(default_factory=list)
    cta: str = ""
    description: str = ""
    thumbnail_prompt: str = ""
    chapter_outline: List[str] = field(default_factory=list)
    retention_notes: List[str] = field(default_factory=list)
    production_notes: List[str] = field(default_factory=list)


@dataclass
class ShortScript:
    short_id: str = ""
    title: str = ""
    hook: str = ""
    beats: List[str] = field(default_factory=list)
    visual_cues: List[str] = field(default_factory=list)
    on_screen_text: List[str] = field(default_factory=list)
    caption: str = ""
    hashtags: List[str] = field(default_factory=list)
    cta: str = ""
    duration_seconds: int = 0
    production_notes: List[str] = field(default_factory=list)


@dataclass
class RepurposedAssets:
    tweets: List[str] = field(default_factory=list)
    linkedin_post: str = ""
    instagram_caption: str = ""
    tiktok_script: str = ""
    blog_outline: List[str] = field(default_factory=list)
    blog_article: str = ""


@dataclass
class ContentPackage:
    brief: ContentBrief = field(default_factory=ContentBrief)
    long_form: LongFormScript = field(default_factory=LongFormScript)
    shorts: List[ShortScript] = field(default_factory=list)
    repurposed: RepurposedAssets = field(default_factory=RepurposedAssets)
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    source_analysis_ids: List[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    run_id: str = ""
    generated_at: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)
    research_summary: Dict[str, Any] = field(default_factory=dict)
    videos: List[VideoCandidate] = field(default_factory=list)
    analyses: List[VideoAnalysis] = field(default_factory=list)
    briefs: List[ContentBrief] = field(default_factory=list)
    packages: List[ContentPackage] = field(default_factory=list)
    pdf_path: str = ""
    manifest_path: str = ""

