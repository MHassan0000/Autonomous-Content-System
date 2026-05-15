# Autonomous Content System

WAT-based Python workflow for an AI-niche YouTube content studio.

## What It Does

- Researches trending AI content from public YouTube data
- Extracts transcripts with free/open-source tooling
- Analyzes viral patterns and hooks
- Generates long-form scripts and Shorts scripts
- Repurposes content into social assets and blog copy
- Renders a polished PDF report plus JSON manifest

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.local.example` to `.env.local` and set `OPENROUTER_API_KEY`.
4. Run: `python tools/run_pipeline.py`
5. Launch UI: `python tools/run_ui.py`

Default free OpenRouter model: `openai/gpt-oss-120b:free`

Local UI: `http://localhost:8501`

Restart the UI later with either:

- `python tools/run_ui.py`
- `powershell -ExecutionPolicy Bypass -File tools/start_ui.ps1`

If you want production-safe Modal deployment, create a Modal secret and set `MODAL_SECRET_NAME` in your local `.env.local`.

Useful smoke-test overrides:

- `YOUTUBE_SEARCH_QUERIES=AI news`
- `MAX_CANDIDATE_VIDEOS=3`
- `TOP_VIDEOS_TO_ANALYZE=1`
- `IDEAS_PER_RUN=1`
- `SHORTS_PER_IDEA=1`

## Output

- PDF report: `.tmp/output/<run_id>/report.pdf`
- JSON manifest: `.tmp/output/<run_id>/manifest.json`

To fetch the latest Modal-generated PDF back to your machine:

`python tools/download_latest_modal_report.py`
