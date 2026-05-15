from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .models import ContentBrief, ContentPackage, PipelineResult, ShortScript, VideoAnalysis, VideoCandidate
from .utils import ensure_dir, format_number, normalize_whitespace, truncate_text


class PDFReportBuilder:
    def __init__(self, settings: Any):
        self.settings = settings

    def build(self, result: PipelineResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        ensure_dir(output_path.parent)

        doc = BaseDocTemplate(str(output_path), pagesize=LETTER, title=result.settings.get("report_title", "Autonomous Content Studio"))
        styles = self._styles()
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
        doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._decorate_page)])

        story = []
        story.extend(self._title_block(result, styles))
        story.append(Spacer(1, 0.2 * inch))
        story.extend(self._summary_block(result, styles))
        story.append(PageBreak())
        story.extend(self._ranked_videos_block(result, styles))
        story.append(PageBreak())
        story.extend(self._briefs_block(result, styles))
        story.append(PageBreak())
        story.extend(self._packages_block(result, styles))
        story.append(PageBreak())
        story.extend(self._appendix_block(result, styles))

        doc.build(story)
        return output_path

    def _styles(self):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=colors.HexColor("#111827"), spaceAfter=12))
        styles.add(ParagraphStyle(name="SubtitleCenter", parent=styles["Normal"], alignment=TA_CENTER, fontName="Helvetica", fontSize=11, leading=14, textColor=colors.HexColor("#4B5563"), spaceAfter=8))
        styles.add(ParagraphStyle(name="SectionHeader", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#111827"), spaceAfter=10))
        styles.add(ParagraphStyle(name="CardTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#111827"), spaceAfter=4))
        styles.add(ParagraphStyle(name="BodySmall", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#1F2937"), spaceAfter=4))
        styles.add(ParagraphStyle(name="BodyTiny", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.2, leading=10.2, textColor=colors.HexColor("#374151"), spaceAfter=2))
        styles.add(ParagraphStyle(name="MonoTiny", parent=styles["BodyText"], fontName="Courier", fontSize=8.0, leading=10.0, textColor=colors.HexColor("#111827"), spaceAfter=2))
        return styles

    def _decorate_page(self, canvas, doc):
        canvas.saveState()
        width, height = LETTER
        canvas.setFillColor(colors.HexColor("#0F172A"))
        canvas.rect(0, height - 0.55 * inch, width, 0.55 * inch, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(doc.leftMargin, height - 0.36 * inch, self.settings.report_title)
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(width - doc.rightMargin, height - 0.36 * inch, f"Page {canvas.getPageNumber()}")
        canvas.setFillColor(colors.HexColor("#E5E7EB"))
        canvas.rect(0, 0, width, 0.22 * inch, stroke=0, fill=1)
        canvas.restoreState()

    def _title_block(self, result: PipelineResult, styles):
        items = [
            Paragraph(self._esc(result.settings.get("report_title", "Autonomous Content Studio")), styles["TitleCenter"]),
            Paragraph(self._esc("AI-niche YouTube content research, analysis, scripts, Shorts, and repurposed assets"), styles["SubtitleCenter"]),
            Paragraph(self._esc(f"Run ID: {result.run_id}"), styles["SubtitleCenter"]),
            Paragraph(self._esc(f"Generated: {result.generated_at}"), styles["SubtitleCenter"]),
        ]
        return items

    def _summary_block(self, result: PipelineResult, styles):
        summary = result.research_summary or {}
        stats = [
            ["Candidates", str(summary.get("candidate_count", 0))],
            ["Analyzed", str(summary.get("analyzed_count", 0))],
            ["Briefs", str(summary.get("brief_count", 0))],
            ["Packages", str(summary.get("package_count", 0))],
        ]
        table = Table(stats, colWidths=[2.2 * inch, 2.8 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E0F2FE")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEADING", (0, 0), (-1, -1), 11),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#111827")),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        items = [Paragraph("Executive Summary", styles["SectionHeader"]), table]
        if summary.get("top_insights"):
            for insight in summary["top_insights"]:
                items.append(Paragraph(self._esc(f"• {insight}"), styles["BodySmall"]))
        return items

    def _ranked_videos_block(self, result: PipelineResult, styles):
        items = [Paragraph("Ranked Research", styles["SectionHeader"])]
        for idx, video in enumerate(result.videos, start=1):
            score = f"{video.trend_score:.1f}" if video.trend_score else "0.0"
            details = (
                f"{video.channel or 'Unknown channel'} | {format_number(video.view_count)} views | "
                f"{video.age_days:.1f} days old | score {score}"
            )
            card = [
                Paragraph(self._esc(f"{idx}. {video.title}"), styles["CardTitle"]),
                Paragraph(self._esc(details), styles["BodyTiny"]),
                Paragraph(self._esc(truncate_text(video.description or "", 500)), styles["BodyTiny"]),
                Spacer(1, 0.08 * inch),
            ]
            items.extend(card)
        return items

    def _briefs_block(self, result: PipelineResult, styles):
        items = [Paragraph("Content Briefs", styles["SectionHeader"])]
        for brief in result.briefs:
            block = [
                Paragraph(self._esc(brief.topic), styles["CardTitle"]),
                Paragraph(self._esc(f"Angle: {brief.angle}"), styles["BodySmall"]),
                Paragraph(self._esc(f"Promise: {brief.promise}"), styles["BodySmall"]),
                Paragraph(self._esc(f"Hook: {brief.hook_strategy}"), styles["BodySmall"]),
                Paragraph(self._esc(f"Why now: {brief.why_now}"), styles["BodySmall"]),
                Paragraph(self._esc(f"Outline: {' | '.join(brief.outline)}"), styles["BodyTiny"]),
                Spacer(1, 0.10 * inch),
            ]
            items.extend(block)
        return items

    def _packages_block(self, result: PipelineResult, styles):
        items = [Paragraph("Generated Assets", styles["SectionHeader"])]
        for package in result.packages:
            items.append(Paragraph(self._esc(package.brief.topic), styles["CardTitle"]))
            items.append(Paragraph(self._esc(f"Score: {package.score:.1f}"), styles["BodySmall"]))
            if package.long_form.title_options:
                items.append(Paragraph(self._esc("Long-form titles"), styles["BodyTiny"]))
                for title in package.long_form.title_options[:3]:
                    items.append(Paragraph(self._esc(f"• {title}"), styles["BodyTiny"]))
            if package.long_form.hook:
                items.append(Paragraph(self._esc(f"Hook: {package.long_form.hook}"), styles["BodySmall"]))
            if package.shorts:
                items.append(Paragraph(self._esc("Shorts"), styles["BodyTiny"]))
                for short in package.shorts:
                    items.append(Paragraph(self._esc(f"• {short.title} - {short.hook}"), styles["BodyTiny"]))
            if package.repurposed.tweets:
                items.append(Paragraph(self._esc("Repurposed snippets"), styles["BodyTiny"]))
                for tweet in package.repurposed.tweets[:3]:
                    items.append(Paragraph(self._esc(f"• {tweet}"), styles["BodyTiny"]))
            items.append(Spacer(1, 0.12 * inch))
        return items

    def _appendix_block(self, result: PipelineResult, styles):
        items = [Paragraph("Appendix", styles["SectionHeader"])]
        for video in result.videos:
            items.append(Paragraph(self._esc(f"{video.video_id} - {video.title}"), styles["BodyTiny"]))
        items.append(Spacer(1, 0.12 * inch))
        items.append(Paragraph(self._esc("Manifest saved alongside this report for structured reuse in SaaS workflows."), styles["BodyTiny"]))
        return items

    def _esc(self, text: str) -> str:
        return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
