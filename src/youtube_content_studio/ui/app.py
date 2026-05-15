from __future__ import annotations

import asyncio
import html
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from youtube_content_studio.config import load_settings  # noqa: E402
from youtube_content_studio.pipeline import run_pipeline  # noqa: E402
from youtube_content_studio.ui.state import default_ui_state, result_to_summary  # noqa: E402
from youtube_content_studio.utils import serialize_for_json, truncate_text  # noqa: E402


st.set_page_config(page_title="Autonomous Content Studio", page_icon="🎬", layout="wide")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .hero {
            padding: 1.4rem 1.5rem;
            border-radius: 24px;
            background: linear-gradient(135deg, #0f172a 0%, #111827 45%, #0f766e 100%);
            color: white;
            box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
            margin-bottom: 1rem;
        }
        .hero-title {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }
        .hero-subtitle {
            font-size: 0.95rem;
            opacity: 0.9;
            margin-bottom: 0.85rem;
        }
        .chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        .chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.18);
            font-size: 0.82rem;
            color: white;
        }
        .section-card {
            padding: 1rem 1rem 0.25rem 1rem;
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 18px;
            background: rgba(248, 250, 252, 0.65);
            margin-bottom: 1rem;
        }
        .section-label {
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #475569;
            margin-bottom: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _chip(label: str, value: str) -> str:
    return f'<span class="chip"><strong>{html.escape(label)}:</strong> {html.escape(value)}</span>'


def _render_hero(settings, state):
    chips = [
        _chip("Model", settings.openrouter_model),
        _chip("Queries", str(len(settings.youtube_search_queries))),
        _chip("Output", str(settings.resolved_output_dir())),
        _chip("Mode", "Smoke" if st.session_state.get("smoke_test_mode", False) else "Full"),
    ]
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-title">Autonomous Content Studio</div>
            <div class="hero-subtitle">AI niche workflow for research, analysis, scripts, Shorts, repurposing, and PDF reporting.</div>
            <div class="chip-row">{''.join(chips)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section(title: str, subtitle: str | None = None):
    st.markdown(f'<div class="section-label">{html.escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def _load_state() -> dict[str, Any]:
    if "studio_state" not in st.session_state:
        st.session_state.studio_state = default_ui_state()
    return st.session_state.studio_state


def _push_event(event: str, data: dict[str, Any]) -> None:
    state = _load_state()
    state["events"].append({"event": event, **data})
    if "progress" in data:
        state["progress"] = float(data["progress"])
    if "message" in data:
        state["message"] = str(data["message"])
    state["status"] = event.replace("_", " ").title()


def _run_workflow(settings) -> Any:
    return asyncio.run(run_pipeline(settings, event_callback=_push_event))


def _settings_from_form(base_settings):
    settings = base_settings
    settings.report_title = st.session_state.get("report_title", settings.report_title)
    settings.openrouter_model = st.session_state.get("openrouter_model", settings.openrouter_model)
    settings.youtube_search_queries = [q.strip() for q in st.session_state.get("youtube_search_queries", "").split(",") if q.strip()]
    settings.max_candidate_videos = int(st.session_state.get("max_candidate_videos", settings.max_candidate_videos))
    settings.top_videos_to_analyze = int(st.session_state.get("top_videos_to_analyze", settings.top_videos_to_analyze))
    settings.ideas_per_run = int(st.session_state.get("ideas_per_run", settings.ideas_per_run))
    settings.shorts_per_idea = int(st.session_state.get("shorts_per_idea", settings.shorts_per_idea))
    settings.search_results_per_query = int(st.session_state.get("search_results_per_query", settings.search_results_per_query))
    settings.full_info_concurrency = int(st.session_state.get("full_info_concurrency", settings.full_info_concurrency))
    settings.llm_concurrency = int(st.session_state.get("llm_concurrency", settings.llm_concurrency))
    settings.transcript_backend = st.session_state.get("transcript_backend", settings.transcript_backend)
    settings.transcript_language = st.session_state.get("transcript_language", settings.transcript_language)
    settings.skip_video_metadata = bool(st.session_state.get("skip_video_metadata", settings.skip_video_metadata))
    settings.skip_transcripts = bool(st.session_state.get("skip_transcripts", settings.skip_transcripts))
    settings.llm_temperature = float(st.session_state.get("llm_temperature", settings.llm_temperature))
    return settings


def _sidebar(settings):
    st.sidebar.title("Control Panel")
    st.sidebar.caption("Run research, scripts, and the PDF report from one place.")

    st.sidebar.text_input("Report title", key="report_title", value=settings.report_title)
    st.sidebar.text_input("OpenRouter model", key="openrouter_model", value=settings.openrouter_model)
    st.sidebar.text_input("Search queries", key="youtube_search_queries", value=", ".join(settings.youtube_search_queries))
    st.sidebar.number_input("Candidate videos", min_value=1, max_value=100, key="max_candidate_videos", value=settings.max_candidate_videos)
    st.sidebar.number_input("Top videos to analyze", min_value=1, max_value=20, key="top_videos_to_analyze", value=settings.top_videos_to_analyze)
    st.sidebar.number_input("Ideas per run", min_value=1, max_value=10, key="ideas_per_run", value=settings.ideas_per_run)
    st.sidebar.number_input("Shorts per idea", min_value=1, max_value=5, key="shorts_per_idea", value=settings.shorts_per_idea)
    st.sidebar.number_input("Search results per query", min_value=1, max_value=20, key="search_results_per_query", value=settings.search_results_per_query)
    st.sidebar.number_input("Metadata concurrency", min_value=1, max_value=16, key="full_info_concurrency", value=settings.full_info_concurrency)
    st.sidebar.number_input("LLM concurrency", min_value=1, max_value=8, key="llm_concurrency", value=settings.llm_concurrency)
    st.sidebar.selectbox("Transcript backend", ["auto", "yt-dlp", "api"], key="transcript_backend", index=["auto", "yt-dlp", "api"].index(settings.transcript_backend if settings.transcript_backend in ["auto", "yt-dlp", "api"] else "auto"))
    st.sidebar.text_input("Transcript language", key="transcript_language", value=settings.transcript_language)
    st.sidebar.slider("LLM temperature", min_value=0.0, max_value=1.0, step=0.05, key="llm_temperature", value=float(settings.llm_temperature))
    st.sidebar.checkbox("Skip video metadata (fast mode)", key="skip_video_metadata", value=settings.skip_video_metadata)
    st.sidebar.checkbox("Skip transcripts (fast mode)", key="skip_transcripts", value=settings.skip_transcripts)
    st.sidebar.divider()
    smoke = st.sidebar.checkbox("Smoke test mode", value=False, key="smoke_test_mode")
    return smoke


def _render_overview_tab(settings, state, result):
    _section("Run Control", "Launch the workflow and monitor the current session.")
    control_col, status_col = st.columns([1.1, 1])
    with control_col:
        run_clicked = st.button("Run Workflow", type="primary", use_container_width=True)
        clear_clicked = st.button("Clear Session", use_container_width=True)
        st.caption("The workflow runs the same engine used by the CLI and produces a PDF plus JSON manifest.")
    with status_col:
        st.metric("Progress", f"{state['progress']:.0%}")
        st.metric("Status", state["status"])
        st.metric("Events", len(state["events"]))
        st.progress(float(state.get("progress", 0.0)))
        st.info(state["message"])

    st.divider()
    left, right = st.columns(2)
    with left:
        _section("Current Settings", "Inputs that control the run.")
        st.write(
            {
                "model": settings.openrouter_model,
                "queries": settings.youtube_search_queries,
                "candidate_videos": settings.max_candidate_videos,
                "top_videos": settings.top_videos_to_analyze,
                "ideas": settings.ideas_per_run,
                "shorts_per_idea": settings.shorts_per_idea,
                "skip_metadata": settings.skip_video_metadata,
                "skip_transcripts": settings.skip_transcripts,
            }
        )
    with right:
        _section("Latest Output", "Generated artifacts from the most recent successful run.")
        if result:
            summary = result_to_summary(result)
            c1, c2 = st.columns(2)
            c1.metric("Briefs", summary["brief_count"])
            c2.metric("Packages", summary["package_count"])
            st.code(summary.get("pdf_path", ""))
        else:
            st.caption("No output yet. Run the workflow to generate a report.")

    return run_clicked, clear_clicked


def _analysis_rows(result):
    rows = []
    for analysis in result.analyses:
        rows.append(
            {
                "Video ID": analysis.video_id,
                "Hook Type": analysis.hook_type,
                "Hook Strength": analysis.hook_strength,
                "Promise": truncate_text(analysis.promise, 90),
                "Angle": truncate_text(analysis.topic_angle, 90),
                "Score": analysis.score,
            }
        )
    return rows


def _video_rows(result):
    rows = []
    for video in result.videos:
        rows.append(
            {
                "Title": video.title,
                "Channel": video.channel,
                "Trend Score": video.trend_score,
                "Views": video.view_count,
                "Age (days)": round(video.age_days, 1),
                "Signals": video.search_signal_count,
                "Transcript": video.transcript_source or "-",
            }
        )
    return rows


def _render_research_tab(result):
    _section("Research Summary", "Ranked candidate videos and viral pattern analysis.")
    st.json(result.research_summary or {})
    if not result:
        return
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Ranked Videos")
        st.dataframe(_video_rows(result), use_container_width=True, hide_index=True)
    with c2:
        st.subheader("Analysis Scores")
        st.dataframe(_analysis_rows(result), use_container_width=True, hide_index=True)


def _render_scripts_tab(result):
    _section("Generated Scripts", "Long-form packages, Shorts, and repurposed content.")
    if not result:
        st.caption("Run the workflow to generate scripts.")
        return

    for package in result.packages:
        with st.expander(f"{package.brief.topic}  |  Score {package.score:.1f}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Brief**")
                st.write(
                    {
                        "angle": package.brief.angle,
                        "promise": package.brief.promise,
                        "hook": package.brief.hook_strategy,
                        "outline": package.brief.outline,
                        "thumbnail_prompt": package.brief.thumbnail_prompt,
                    }
                )
                st.markdown("**Long-form**")
                st.write(package.long_form.title_options)
                st.write(package.long_form.hook)
                st.write(package.long_form.intro)
                for section in package.long_form.sections:
                    st.markdown(f"- **{section.get('heading', '')}**: {section.get('narration', '')}")
            with col2:
                st.markdown("**Shorts**")
                for short in package.shorts:
                    st.markdown(f"- **{short.title}**: {short.hook}")
                    st.caption(f"CTA: {short.cta}")
                st.markdown("**Repurposed Assets**")
                st.write({
                    "tweets": package.repurposed.tweets,
                    "linkedin_post": truncate_text(package.repurposed.linkedin_post, 400),
                    "instagram_caption": truncate_text(package.repurposed.instagram_caption, 400),
                    "tiktok_script": truncate_text(package.repurposed.tiktok_script, 400),
                })


def _render_outputs_tab(result):
    _section("Outputs", "Download the PDF report and inspect the JSON manifest.")
    if not result:
        st.caption("No output yet.")
        return
    summary = result_to_summary(result)
    c1, c2 = st.columns(2)
    with c1:
        pdf_path = summary.get("pdf_path")
        st.markdown("**PDF Report**")
        st.code(pdf_path or "")
        if pdf_path and Path(pdf_path).exists():
            with open(pdf_path, "rb") as fh:
                st.download_button("Download PDF", fh, file_name=Path(pdf_path).name, mime="application/pdf", use_container_width=True)
    with c2:
        manifest_path = summary.get("manifest_path")
        st.markdown("**Manifest**")
        st.code(manifest_path or "")
        if manifest_path and Path(manifest_path).exists():
            with open(manifest_path, "rb") as fh:
                st.download_button("Download Manifest", fh, file_name=Path(manifest_path).name, mime="application/json", use_container_width=True)
    st.markdown("**Manifest Preview**")
    st.json(serialize_for_json(result))


def _render_history_tab(state):
    _section("Run History", "Session timeline and past completed runs.")
    if state["run_history"]:
        st.dataframe(state["run_history"], use_container_width=True, hide_index=True)
    else:
        st.caption("No previous runs in this session.")
    st.markdown("**Event Log**")
    if state["events"]:
        st.dataframe(state["events"][-100:], use_container_width=True, hide_index=True)
    else:
        st.caption("No events yet.")


def _render_settings_tab(settings):
    _section("Settings", "Current resolved configuration and environment inputs.")
    st.json(settings.to_dict())
    st.caption("Trigger type: prompt/manual. Click Run Workflow in the UI, or run the CLI entrypoint.")


def _render_completed_summary(result):
    if not result:
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", len(result.videos))
    c2.metric("Analyses", len(result.analyses))
    c3.metric("Briefs", len(result.briefs))
    c4.metric("Packages", len(result.packages))


def main():
    _inject_styles()
    state = _load_state()
    settings = state["settings"]
    smoke = _sidebar(settings)
    _render_hero(settings, state)

    result = state.get("last_result")
    if result:
        _render_completed_summary(result)

    tab_overview, tab_research, tab_scripts, tab_outputs, tab_history, tab_settings = st.tabs(
        ["Overview", "Research", "Scripts", "Outputs", "History", "Settings"]
    )

    with tab_overview:
        run_clicked, clear_clicked = _render_overview_tab(settings, state, result)

    if clear_clicked:
        state["events"] = []
        state["progress"] = 0.0
        state["status"] = "Idle"
        state["message"] = "Ready to run."
        state["last_result"] = None
        state["run_history"] = []
        st.rerun()

    if run_clicked:
        live_settings = _settings_from_form(settings)
        if smoke:
            live_settings.youtube_search_queries = live_settings.youtube_search_queries[:1] or ["AI news"]
            live_settings.max_candidate_videos = min(live_settings.max_candidate_videos, 3)
            live_settings.top_videos_to_analyze = min(live_settings.top_videos_to_analyze, 1)
            live_settings.ideas_per_run = min(live_settings.ideas_per_run, 1)
            live_settings.shorts_per_idea = min(live_settings.shorts_per_idea, 1)
            live_settings.search_results_per_query = min(live_settings.search_results_per_query, 3)
            live_settings.skip_video_metadata = True
            live_settings.skip_transcripts = True

        state["events"] = []
        state["progress"] = 0.0
        state["status"] = "Running"
        state["message"] = "Starting workflow..."
        with st.spinner("Running workflow..."):
            try:
                result = _run_workflow(live_settings)
                state["last_result"] = result
                state["run_history"].append(result_to_summary(result))
                state["status"] = "Completed"
                state["message"] = "Workflow completed successfully."
                state["progress"] = 1.0
            except Exception as exc:
                state["status"] = "Failed"
                state["message"] = str(exc)
                st.exception(exc)

        st.rerun()

    with tab_research:
        _render_research_tab(state.get("last_result"))

    with tab_scripts:
        _render_scripts_tab(state.get("last_result"))

    with tab_outputs:
        _render_outputs_tab(state.get("last_result"))

    with tab_history:
        _render_history_tab(state)

    with tab_settings:
        _render_settings_tab(settings)


if __name__ == "__main__":
    main()
