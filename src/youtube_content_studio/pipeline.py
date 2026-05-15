from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import AnalysisEngine
from .cache import SQLiteCache
from .config import Settings
from .generation import ContentGenerator
from .logger import setup_logging
from .models import ContentBrief, ContentPackage, PipelineResult, TranscriptDocument, VideoAnalysis, VideoCandidate
from .openrouter import OpenRouterClient
from .pdf_report import PDFReportBuilder
from .scoring import ScoringEngine
from .transcript import TranscriptExtractor
from .utils import ensure_dir, serialize_for_json, sha256_text
from .youtube_search import YouTubeResearcher, YouTubeVideoLoader


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.output_dir = ensure_dir(Path(settings.resolved_output_dir()) / self.run_id)
        self.logger = setup_logging("youtube_content_studio", settings.log_level, self.output_dir, self.run_id)
        self.cache = SQLiteCache(settings.resolved_cache_path())
        self.client = OpenRouterClient(settings, cache=self.cache, logger=self.logger)
        self.researcher = YouTubeResearcher(settings, cache=self.cache, logger=self.logger)
        self.video_loader = YouTubeVideoLoader(settings, cache=self.cache, logger=self.logger)
        self.transcript_extractor = TranscriptExtractor(settings, cache=self.cache, logger=self.logger)
        self.analysis_engine = AnalysisEngine(settings, self.client, cache=self.cache, logger=self.logger)
        self.generator = ContentGenerator(settings, self.client, cache=self.cache, logger=self.logger)
        self.report_builder = PDFReportBuilder(settings)
        self.scorer = ScoringEngine()

    async def run(self) -> PipelineResult:
        self.logger.info("Starting pipeline run %s", self.run_id)

        candidates = await self._research()
        loaded_candidates = await self._load_metadata(candidates)
        ranked_candidates = self._rank_candidates(loaded_candidates)

        transcripts = await self._extract_transcripts(ranked_candidates[: self.settings.top_videos_to_analyze])
        research_summary = self._build_research_summary(ranked_candidates)

        analyses = await self.analysis_engine.analyze_many(ranked_candidates[: self.settings.top_videos_to_analyze], transcripts, research_summary)
        ranked_analyses = self._rank_analyses(ranked_candidates[: self.settings.top_videos_to_analyze], analyses)

        briefs = await self.generator.generate_briefs(research_summary, ranked_analyses, count=self.settings.ideas_per_run)
        packages = await self._generate_packages(briefs, ranked_analyses, ranked_candidates)

        research_summary = self._finalize_research_summary(research_summary, ranked_analyses, briefs, packages)

        result = PipelineResult(
            run_id=self.run_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            settings=self.settings.to_dict(),
            research_summary=research_summary,
            videos=ranked_candidates,
            analyses=ranked_analyses,
            briefs=briefs,
            packages=packages,
        )

        result.pdf_path = str(self.report_builder.build(result, self.output_dir / "report.pdf"))
        result.manifest_path = str(self._write_manifest(result))
        self.logger.info("Pipeline complete: %s", result.pdf_path)
        return result

    async def close(self) -> None:
        await self.researcher.close()
        self.cache.close()

    async def _research(self) -> list[VideoCandidate]:
        self.logger.info("Researching YouTube results")
        return await self.researcher.search(self.settings.youtube_search_queries)

    async def _load_metadata(self, candidates: list[VideoCandidate]) -> list[VideoCandidate]:
        if not candidates:
            return []
        if self.settings.skip_video_metadata:
            return candidates
        sem = asyncio.Semaphore(self.settings.full_info_concurrency)

        async def _load(candidate: VideoCandidate):
            async with sem:
                return await self.video_loader.fetch_video_metadata(candidate)

        loaded = await asyncio.gather(*[_load(candidate) for candidate in candidates])
        return loaded

    def _rank_candidates(self, candidates: list[VideoCandidate]) -> list[VideoCandidate]:
        for candidate in candidates:
            candidate.trend_score, breakdown = self.scorer.score_video_candidate(candidate)
            candidate.analysis = breakdown
        return sorted(candidates, key=lambda item: item.trend_score, reverse=True)

    async def _extract_transcripts(self, candidates: list[VideoCandidate]) -> dict[str, TranscriptDocument]:
        if self.settings.skip_transcripts:
            transcripts: dict[str, TranscriptDocument] = {}
            for candidate in candidates:
                fallback_text = f"{candidate.title} {candidate.description}".strip()
                transcripts[candidate.video_id] = TranscriptDocument(
                    video_id=candidate.video_id,
                    language=self.settings.transcript_language,
                    source="skipped",
                    segments=[],
                    text=fallback_text,
                    word_count=len(fallback_text.split()),
                    excerpt=fallback_text[: self.settings.transcript_excerpt_chars],
                )
            return transcripts
        sem = asyncio.Semaphore(self.settings.full_info_concurrency)

        async def _extract(candidate: VideoCandidate):
            async with sem:
                transcript = await self.transcript_extractor.extract(candidate)
                candidate.transcript_text = transcript.text
                candidate.transcript_segments = transcript.segments
                candidate.transcript_source = transcript.source
                return candidate.video_id, transcript

        items = await asyncio.gather(*[_extract(candidate) for candidate in candidates])
        return {video_id: transcript for video_id, transcript in items}

    def _build_research_summary(self, candidates: list[VideoCandidate]) -> dict[str, Any]:
        if not candidates:
            return {
                "research_id": sha256_text(self.run_id),
                "candidate_count": 0,
                "analyzed_count": 0,
                "brief_count": 0,
                "package_count": 0,
                "top_insights": ["No candidates were found."],
            }

        top = candidates[: min(5, len(candidates))]
        total_views = sum(c.view_count for c in candidates)
        avg_trend = sum(c.trend_score for c in candidates) / len(candidates)
        common_terms = {}
        for candidate in top:
            words = (candidate.title + " " + candidate.description).lower().split()
            for word in words:
                if len(word) < 4:
                    continue
                common_terms[word] = common_terms.get(word, 0) + 1
        ranked_terms = sorted(common_terms.items(), key=lambda item: (-item[1], item[0]))[:8]
        top_insights = [
            f"Average trend score: {avg_trend:.1f}",
            f"Total views across candidates: {total_views:,}",
            f"Top repeated terms: {', '.join(term for term, _ in ranked_terms) if ranked_terms else 'n/a'}",
        ]
        return {
            "research_id": sha256_text(self.run_id),
            "candidate_count": len(candidates),
            "analyzed_count": 0,
            "brief_count": 0,
            "package_count": 0,
            "top_insights": top_insights,
        }

    def _finalize_research_summary(self, summary: dict[str, Any], analyses: list[VideoAnalysis], briefs: list[ContentBrief], packages: list[ContentPackage]) -> dict[str, Any]:
        summary = dict(summary)
        summary["analyzed_count"] = len(analyses)
        summary["brief_count"] = len(briefs)
        summary["package_count"] = len(packages)
        return summary

    def _rank_analyses(self, candidates: list[VideoCandidate], analyses: list[VideoAnalysis]) -> list[VideoAnalysis]:
        candidate_map = {candidate.video_id: candidate for candidate in candidates}
        for analysis in analyses:
            candidate = candidate_map.get(analysis.video_id)
            if not candidate:
                continue
            score, breakdown = self.scorer.score_analysis(candidate, analysis)
            analysis.score = score
            analysis.raw = {**analysis.raw, "score_breakdown": breakdown}
        return sorted(analyses, key=lambda item: item.score, reverse=True)

    async def _generate_packages(self, briefs: list[ContentBrief], analyses: list[VideoAnalysis], candidates: list[VideoCandidate]) -> list[ContentPackage]:
        sem = asyncio.Semaphore(self.settings.llm_concurrency)

        async def _generate(brief: ContentBrief):
            async with sem:
                return await self.generator.generate_package(brief, analyses, candidates)

        packages = await asyncio.gather(*[_generate(brief) for brief in briefs])
        return sorted(packages, key=lambda item: item.score, reverse=True)

    def _write_manifest(self, result: PipelineResult) -> Path:
        manifest_path = self.output_dir / "manifest.json"
        payload = serialize_for_json(result)
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        return manifest_path


async def run_pipeline(settings: Settings) -> PipelineResult:
    pipeline = Pipeline(settings)
    try:
        result = await pipeline.run()
        return result
    finally:
        await pipeline.close()
