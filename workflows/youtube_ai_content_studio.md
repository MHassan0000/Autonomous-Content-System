# YouTube AI Content Studio Workflow

## Objective

Build a fully autonomous AI-niche YouTube content generation report using public YouTube data and OpenRouter for all LLM reasoning.

## Required Inputs

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `YOUTUBE_SEARCH_QUERIES`
- `CACHE_DB_PATH`
- `OUTPUT_DIR`

## Tools

- `tools/run_pipeline.py` - primary runner
- `src/youtube_content_studio/` - workflow modules

## Stage Order

1. Research public YouTube search results for AI topics.
2. Rank candidates using trend heuristics.
3. Extract transcripts with `youtube-transcript-api` or `yt-dlp` caption fallback.
4. Analyze viral hooks, structure, retention devices, and audience promise with OpenRouter.
5. Generate content briefs for long-form and Shorts.
6. Generate scripts, titles, hooks, descriptions, CTAs, and thumbnail prompts.
7. Repurpose the winning content into social and blog assets.
8. Score and rank the final outputs.
9. Render a professional PDF report and save a JSON manifest.

## Edge Cases

- If transcripts are missing, fall back to title/description/chapters and note limited confidence.
- If YouTube search returns few results, reduce candidate thresholds and continue.
- If OpenRouter returns invalid JSON, repair the payload and retry.
- If a subtitle track is unavailable, use the best caption track or generate a transcript summary from metadata.

## Outputs

- `report.pdf`
- `manifest.json`
- intermediate caches in `.tmp/`
