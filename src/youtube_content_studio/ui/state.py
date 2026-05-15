from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..config import load_settings
from ..models import PipelineResult
from ..utils import serialize_for_json


def default_ui_state() -> dict[str, Any]:
    settings = load_settings()
    return {
        "settings": settings,
        "last_result": None,
        "events": [],
        "progress": 0.0,
        "status": "Idle",
        "message": "Ready to run.",
        "run_history": [],
    }


def result_to_summary(result: PipelineResult) -> dict[str, Any]:
    return {
        "run_id": result.run_id,
        "generated_at": result.generated_at,
        "pdf_path": result.pdf_path,
        "manifest_path": result.manifest_path,
        "candidate_count": len(result.videos),
        "analysis_count": len(result.analyses),
        "brief_count": len(result.briefs),
        "package_count": len(result.packages),
        "settings": result.settings,
        "research_summary": result.research_summary,
    }
