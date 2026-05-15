from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys

import modal
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

load_dotenv(ROOT / ".env.local")

from youtube_content_studio.config import load_settings  # noqa: E402
from youtube_content_studio.pipeline import run_pipeline  # noqa: E402


APP_NAME = "autonomous-content-system"
OUTPUT_VOLUME_NAME = "autonomous-content-system-output"
OUTPUT_MOUNT_PATH = "/data"
WEEKLY_CRON = os.getenv("MODAL_WEEKLY_CRON", "0 6 * * 1")
WEEKLY_TIMEZONE = os.getenv("MODAL_TIMEZONE", "UTC")
MODAL_SECRET_NAME = os.getenv("MODAL_SECRET_NAME", "").strip()

app = modal.App(APP_NAME)
output_volume = modal.Volume.from_name(OUTPUT_VOLUME_NAME, create_if_missing=True)


def _deployment_secret():
    if MODAL_SECRET_NAME:
        return modal.Secret.from_name(MODAL_SECRET_NAME)
    return modal.Secret.from_dotenv(ROOT, filename=".env.local")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(ROOT / "requirements.txt"))
    .add_local_dir(str(ROOT / "src"), remote_path="/root/src")
    .add_local_file(str(ROOT / "modal_app.py"), remote_path="/root/modal_app.py")
)


def _load_runtime_settings():
    settings = load_settings()
    settings.output_dir = Path(OUTPUT_MOUNT_PATH) / "output"
    settings.cache_db_path = Path(OUTPUT_MOUNT_PATH) / "cache.sqlite3"
    settings.skip_video_metadata = bool(str(settings.skip_video_metadata).lower() == "true")
    settings.skip_transcripts = bool(str(settings.skip_transcripts).lower() == "true")
    return settings


@app.function(
    image=image,
    secrets=[_deployment_secret()],
    volumes={OUTPUT_MOUNT_PATH: output_volume},
    schedule=modal.Cron(WEEKLY_CRON, timezone=WEEKLY_TIMEZONE),
    timeout=60 * 60,
)
async def run_content_studio(smoke_test: bool = False) -> dict:
    settings = _load_runtime_settings()
    if smoke_test:
        settings.youtube_search_queries = settings.youtube_search_queries[:1] or ["AI news"]
        settings.max_candidate_videos = min(settings.max_candidate_videos, 3)
        settings.top_videos_to_analyze = min(settings.top_videos_to_analyze, 1)
        settings.ideas_per_run = min(settings.ideas_per_run, 1)
        settings.shorts_per_idea = min(settings.shorts_per_idea, 1)
        settings.search_results_per_query = min(settings.search_results_per_query, 3)
        settings.skip_video_metadata = True
        settings.skip_transcripts = True

    result = await run_pipeline(settings)
    latest_path = Path(OUTPUT_MOUNT_PATH) / "latest.json"
    latest_payload = {
        "run_id": result.run_id,
        "generated_at": result.generated_at,
        "volume_pdf_path": str(Path(result.pdf_path).relative_to(OUTPUT_MOUNT_PATH)),
        "volume_manifest_path": str(Path(result.manifest_path).relative_to(OUTPUT_MOUNT_PATH)),
        "pdf_path": result.pdf_path,
        "manifest_path": result.manifest_path,
    }
    latest_path.write_text(json.dumps(latest_payload, indent=2), encoding="utf-8")
    await output_volume.commit.aio()
    return {
        "run_id": result.run_id,
        "generated_at": result.generated_at,
        "pdf_path": result.pdf_path,
        "manifest_path": result.manifest_path,
        "pdf_exists": Path(result.pdf_path).exists(),
        "manifest_exists": Path(result.manifest_path).exists(),
        "pdf_url": f"modal-volume://{OUTPUT_VOLUME_NAME}/{Path(result.pdf_path).name}",
    }


@app.local_entrypoint()
def main(smoke_test: bool = False):
    settings = _load_runtime_settings()
    print(json.dumps(settings.to_dict(), indent=2))
    if smoke_test:
        result = run_content_studio.remote(smoke_test=True)
    else:
        result = run_content_studio.remote()
    print(json.dumps(result, indent=2))


@app.local_entrypoint(name="deploy")
def deploy_app():
    with modal.enable_output():
        app.deploy()
