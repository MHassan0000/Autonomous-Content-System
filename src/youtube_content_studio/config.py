from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from .utils import ensure_dir


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None and value != "" else default
    except Exception:
        return default


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None and value != "" else default
    except Exception:
        return default


def _split_csv(value: str | None, default: List[str]) -> List[str]:
    if not value:
        return default
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


@dataclass
class Settings:
    project_root: Path
    niche: str = "AI"
    report_title: str = "Autonomous AI Content Studio"
    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_app_name: str = "Autonomous Content Studio"
    openrouter_site_url: str = "http://localhost"
    youtube_search_queries: List[str] = field(default_factory=list)
    max_candidate_videos: int = 24
    top_videos_to_analyze: int = 6
    ideas_per_run: int = 2
    shorts_per_idea: int = 2
    search_results_per_query: int = 6
    full_info_concurrency: int = 4
    llm_concurrency: int = 3
    transcript_backend: str = "auto"
    transcript_language: str = "en"
    transcript_excerpt_chars: int = 7000
    analysis_excerpt_chars: int = 4500
    video_info_timeout_seconds: int = 20
    transcript_timeout_seconds: int = 20
    cache_db_path: Path = Path(".tmp/cache.sqlite3")
    output_dir: Path = Path(".tmp/output")
    log_level: str = "INFO"
    max_llm_retries: int = 3
    request_timeout_seconds: int = 90
    llm_temperature: float = 0.35
    use_playwright_fallback: bool = False
    skip_video_metadata: bool = False
    skip_transcripts: bool = False
    search_modes: List[str] = field(default_factory=lambda: ["relevance", "date"])

    def resolved_output_dir(self) -> Path:
        return ensure_dir(self._resolve_path(self.output_dir))

    def resolved_cache_path(self) -> Path:
        path = self._resolve_path(self.cache_db_path)
        ensure_dir(path.parent)
        return path

    def _resolve_path(self, value: Path) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.project_root / path

    def to_dict(self) -> dict:
        return {
            "niche": self.niche,
            "report_title": self.report_title,
            "openrouter_model": self.openrouter_model,
            "youtube_search_queries": self.youtube_search_queries,
            "max_candidate_videos": self.max_candidate_videos,
            "top_videos_to_analyze": self.top_videos_to_analyze,
            "ideas_per_run": self.ideas_per_run,
            "shorts_per_idea": self.shorts_per_idea,
            "search_results_per_query": self.search_results_per_query,
            "transcript_backend": self.transcript_backend,
            "transcript_language": self.transcript_language,
            "output_dir": str(self._resolve_path(self.output_dir)),
            "cache_db_path": str(self._resolve_path(self.cache_db_path)),
            "log_level": self.log_level,
            "max_llm_retries": self.max_llm_retries,
            "request_timeout_seconds": self.request_timeout_seconds,
            "llm_temperature": self.llm_temperature,
            "use_playwright_fallback": self.use_playwright_fallback,
        }


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=project_root / ".env.local", override=False)
    load_dotenv(dotenv_path=project_root / ".env", override=False)

    default_queries = [
        "AI news",
        "AI tools",
        "AI agents",
        "ChatGPT",
        "OpenAI",
        "generative AI",
        "Claude AI",
        "Gemini AI",
    ]

    settings = Settings(
        project_root=project_root,
        niche=os.getenv("NICHE", os.getenv("NICHe", "AI")),
        report_title=os.getenv("REPORT_TITLE", "Autonomous AI Content Studio"),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-120b:free").strip(),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
        openrouter_app_name=os.getenv("OPENROUTER_APP_NAME", "Autonomous Content Studio").strip(),
        openrouter_site_url=os.getenv("OPENROUTER_SITE_URL", "http://localhost").strip(),
        youtube_search_queries=_split_csv(os.getenv("YOUTUBE_SEARCH_QUERIES"), default_queries),
        max_candidate_videos=_parse_int(os.getenv("MAX_CANDIDATE_VIDEOS"), 24),
        top_videos_to_analyze=_parse_int(os.getenv("TOP_VIDEOS_TO_ANALYZE"), 6),
        ideas_per_run=_parse_int(os.getenv("IDEAS_PER_RUN"), 2),
        shorts_per_idea=_parse_int(os.getenv("SHORTS_PER_IDEA"), 2),
        search_results_per_query=_parse_int(os.getenv("SEARCH_RESULTS_PER_QUERY"), 6),
        full_info_concurrency=_parse_int(os.getenv("FULL_INFO_CONCURRENCY"), 4),
        llm_concurrency=_parse_int(os.getenv("LLM_CONCURRENCY"), 3),
        transcript_backend=os.getenv("TRANSCRIPT_BACKEND", "auto").strip().lower(),
        transcript_language=os.getenv("TRANSCRIPT_LANGUAGE", "en").strip(),
        transcript_excerpt_chars=_parse_int(os.getenv("TRANSCRIPT_EXCERPT_CHARS"), 7000),
        analysis_excerpt_chars=_parse_int(os.getenv("ANALYSIS_EXCERPT_CHARS"), 4500),
        video_info_timeout_seconds=_parse_int(os.getenv("VIDEO_INFO_TIMEOUT_SECONDS"), 20),
        transcript_timeout_seconds=_parse_int(os.getenv("TRANSCRIPT_TIMEOUT_SECONDS"), 20),
        cache_db_path=Path(os.getenv("CACHE_DB_PATH", ".tmp/cache.sqlite3")),
        output_dir=Path(os.getenv("OUTPUT_DIR", ".tmp/output")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        max_llm_retries=_parse_int(os.getenv("MAX_LLM_RETRIES"), 3),
        request_timeout_seconds=_parse_int(os.getenv("REQUEST_TIMEOUT_SECONDS"), 90),
        llm_temperature=_parse_float(os.getenv("LLM_TEMPERATURE"), 0.35),
        use_playwright_fallback=_parse_bool(os.getenv("USE_PLAYWRIGHT_FALLBACK"), False),
        skip_video_metadata=_parse_bool(os.getenv("SKIP_VIDEO_METADATA"), False),
        skip_transcripts=_parse_bool(os.getenv("SKIP_TRANSCRIPTS"), False),
    )

    return settings
