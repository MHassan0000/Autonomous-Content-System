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
3. Copy `.env.example` to `.env` and set `OPENROUTER_API_KEY`.
4. Run: `python tools/run_pipeline.py`

## Output

- PDF report: `.tmp/output/<run_id>/report.pdf`
- JSON manifest: `.tmp/output/<run_id>/manifest.json`
