from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable

from .models import ContentBrief, ContentPackage, VideoAnalysis, VideoCandidate


class ScoringEngine:
    def score_video_candidate(self, video: VideoCandidate) -> tuple[float, dict[str, float]]:
        age = max(video.age_days, 0.0)
        views = max(video.view_count, 1)
        like_count = max(video.like_count, 0)
        comment_count = max(video.comment_count, 0)

        freshness = 1.0 / (1.0 + age / 7.0)
        velocity = math.log10(views + 1.0) / max(age + 1.0, 1.0)
        engagement = (math.log10(like_count + 1.0) + 0.5 * math.log10(comment_count + 1.0)) / 10.0
        search_signal = min(video.search_signal_count / 3.0, 1.0)

        trend_fit = min(100.0, (45.0 * freshness) + (35.0 * min(velocity * 8.0, 1.0)) + (10.0 * min(engagement, 1.0)) + (10.0 * search_signal))
        breakdown = {
            "freshness": round(freshness * 100.0, 2),
            "velocity": round(min(velocity * 8.0, 1.0) * 100.0, 2),
            "engagement": round(min(engagement, 1.0) * 100.0, 2),
            "search_signal": round(search_signal * 100.0, 2),
        }
        return round(trend_fit, 2), breakdown

    def score_analysis(self, video: VideoCandidate, analysis: VideoAnalysis) -> tuple[float, dict[str, float]]:
        hook = max(min(float(analysis.hook_strength), 100.0), 0.0)
        retention_bonus = min(len(analysis.retention_devices) * 8.0, 24.0)
        viral_bonus = min(len(analysis.viral_factors) * 6.0, 18.0)
        clarity = 0.0
        if analysis.promise:
            clarity += 20.0
        if analysis.recommended_angle:
            clarity += 15.0
        if analysis.thumbnail_direction:
            clarity += 10.0
        if analysis.topic_angle:
            clarity += 10.0

        total = min(100.0, (hook * 0.4) + retention_bonus + viral_bonus + clarity)
        breakdown = {
            "hook": round(hook, 2),
            "retention_bonus": round(retention_bonus, 2),
            "viral_bonus": round(viral_bonus, 2),
            "clarity": round(clarity, 2),
        }
        return round(total, 2), breakdown

    def score_brief(self, brief: ContentBrief, analyses: list[VideoAnalysis], videos: list[VideoCandidate]) -> tuple[float, dict[str, float]]:
        source_scores = [video.trend_score for video in videos if video.video_id in set(brief.source_video_ids)]
        trend_fit = sum(source_scores) / len(source_scores) if source_scores else 0.0
        specificity = 0.0
        if brief.topic:
            specificity += 15.0
        if brief.angle:
            specificity += 15.0
        if brief.promise:
            specificity += 15.0
        if brief.outline:
            specificity += min(len(brief.outline) * 4.0, 20.0)
        if brief.thumbnail_prompt:
            specificity += 10.0

        retention = 0.0
        hook_words = (brief.hook_strategy + " " + brief.promise + " " + brief.angle).lower()
        for token in ["curiosity", "contrarian", "mistake", "how to", "step", "before", "after", "why", "secret", "framework", "system", "challenge"]:
            if token in hook_words:
                retention += 8.0
        retention = min(retention, 25.0)

        novelty = 0.0
        if brief.keywords:
            novelty += min(len(set(brief.keywords)) * 2.5, 20.0)
        if "AI" in brief.topic or "ai" in brief.topic.lower():
            novelty += 5.0
        if "agents" in brief.topic.lower() or "workflow" in brief.angle.lower():
            novelty += 5.0

        execution = 15.0
        if brief.target_runtime_minutes:
            execution += 5.0
        if brief.target_short_runtime_seconds:
            execution += 5.0

        total = min(100.0, (trend_fit * 0.35) + specificity + retention + novelty + execution)
        breakdown = {
            "trend_fit": round(trend_fit, 2),
            "specificity": round(specificity, 2),
            "retention": round(retention, 2),
            "novelty": round(novelty, 2),
            "execution": round(execution, 2),
        }
        return round(total, 2), breakdown

    def score_package(self, package: ContentPackage) -> tuple[float, dict[str, float]]:
        brief_score = package.brief.score or 0.0
        script_completeness = 0.0
        if package.long_form.title_options:
            script_completeness += 15.0
        if package.long_form.hook:
            script_completeness += 15.0
        if package.long_form.sections:
            script_completeness += min(len(package.long_form.sections) * 5.0, 25.0)
        if package.shorts:
            script_completeness += min(len(package.shorts) * 10.0, 20.0)
        if package.repurposed.blog_article:
            script_completeness += 10.0

        polish = 10.0
        if package.repurposed.linkedin_post:
            polish += 5.0
        if package.repurposed.instagram_caption:
            polish += 5.0
        if package.repurposed.tiktok_script:
            polish += 5.0

        total = min(100.0, (brief_score * 0.45) + script_completeness + polish)
        breakdown = {
            "brief_score": round(brief_score, 2),
            "script_completeness": round(script_completeness, 2),
            "polish": round(polish, 2),
        }
        return round(total, 2), breakdown

