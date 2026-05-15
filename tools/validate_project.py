from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_content_studio.config import load_settings  # noqa: E402
from youtube_content_studio.models import ContentBrief, ContentPackage, LongFormScript, PipelineResult, RepurposedAssets, ShortScript, VideoAnalysis, VideoCandidate  # noqa: E402
from youtube_content_studio.pdf_report import PDFReportBuilder  # noqa: E402


def main() -> int:
    settings = load_settings()
    builder = PDFReportBuilder(settings)
    result = PipelineResult(
        run_id="validation",
        generated_at="2026-01-01T00:00:00Z",
        settings=settings.to_dict(),
        research_summary={"candidate_count": 1, "analyzed_count": 1, "brief_count": 1, "package_count": 1, "top_insights": ["Validation run"]},
        videos=[VideoCandidate(video_id="abc123def45", title="Test AI Video", channel="Test Channel", view_count=1000, age_days=2.0, trend_score=88.0)],
        analyses=[VideoAnalysis(video_id="abc123def45", hook_type="question", hook_strength=92.0, promise="Useful AI workflow insights")],
        briefs=[ContentBrief(brief_id="brief-1", topic="AI automation", angle="build a content factory", why_now="AI is moving fast", audience="AI builders", promise="Create more in less time", hook_strategy="contrast", outline=["problem", "solution", "workflow"] )],
        packages=[ContentPackage(
            brief=ContentBrief(brief_id="brief-1", topic="AI automation", angle="build a content factory", why_now="AI is moving fast", audience="AI builders", promise="Create more in less time", hook_strategy="contrast", outline=["problem", "solution", "workflow"]),
            long_form=LongFormScript(title_options=["How to Build an AI Content Factory"], hook="Most creators are doing this backwards.", intro="", sections=[{"heading": "Intro", "narration": "...", "visuals": "...", "retention_note": "..."}], cta="Subscribe", description="", thumbnail_prompt="", chapter_outline=["Intro"]),
            shorts=[ShortScript(short_id="s1", title="AI content in 60 seconds", hook="", beats=[""], visual_cues=[""], on_screen_text=[""], caption="", hashtags=["#AI"], cta="" )],
            repurposed=RepurposedAssets(tweets=["AI content factory"], linkedin_post="Post", instagram_caption="Caption", tiktok_script="Script", blog_outline=["Intro"], blog_article="Article"),
            score=90.0,
        )],
    )
    pdf_path = builder.build(result, settings.resolved_output_dir() / "validation" / "report.pdf")
    if not pdf_path.exists():
        print("PDF validation failed")
        return 1
    print(pdf_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
