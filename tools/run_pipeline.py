from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_content_studio.config import load_settings  # noqa: E402
from youtube_content_studio.pipeline import run_pipeline  # noqa: E402


def main() -> int:
    settings = load_settings()
    if not settings.openrouter_api_key:
        print("Missing OPENROUTER_API_KEY in environment or .env")
        return 1

    if os.getenv("SMOKE_TEST", "").strip().lower() in {"1", "true", "yes", "on"}:
        settings.youtube_search_queries = settings.youtube_search_queries[:1] or ["AI news"]
        settings.max_candidate_videos = min(settings.max_candidate_videos, 3)
        settings.top_videos_to_analyze = min(settings.top_videos_to_analyze, 1)
        settings.ideas_per_run = min(settings.ideas_per_run, 1)
        settings.shorts_per_idea = min(settings.shorts_per_idea, 1)
        settings.search_results_per_query = min(settings.search_results_per_query, 3)
        settings.skip_video_metadata = True
        settings.skip_transcripts = True

    result = asyncio.run(run_pipeline(settings))
    print(result.pdf_path)
    print(result.manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
