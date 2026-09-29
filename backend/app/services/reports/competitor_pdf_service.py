import io
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.models.project import Project
from app.models.local_seo import Competitor


class CompetitorPDFService:
    """
    ReportLab PDF generation service for LocalLift Competitor Benchmarking reports.
    """

    # Brand Colors
    PRIMARY = colors.HexColor("#7C3AED")        # Purple Vibrant
    PRIMARY_DARK = colors.HexColor("#4C1D95")   # Dark Purple
    PRIMARY_LIGHT = colors.HexColor("#F5F3FF")  # Light Purple Tint
    ACCENT_GREEN = colors.HexColor("#059669")   # Emerald
    ACCENT_AMBER = colors.HexColor("#D97706")   # Amber
    SLATE_900 = colors.HexColor("#0F172A")
    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    SLATE_100 = colors.HexColor("#F1F5F9")
    SLATE_50 = colors.HexColor("#F8FAFC")

    @classmethod
    def _get_styles(cls) -> Dict[str, ParagraphStyle]:
        sample = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "DocTitle",
                parent=sample["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=cls.PRIMARY_DARK,
                spaceAfter=4
            ),
            "subtitle": ParagraphStyle(
                "DocSubTitle",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=cls.SLATE_500,
                spaceAfter=12
            ),
            "section_heading": ParagraphStyle(
                "SectionHeading",
                parent=sample["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=17,
                textColor=cls.SLATE_900,
                spaceBefore=12,
                spaceAfter=6
            ),
            "body": ParagraphStyle(
                "Body",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=cls.SLATE_700
            ),
            "body_bold": ParagraphStyle(
                "BodyBold",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=13,
                textColor=cls.SLATE_900
            ),
            "table_cell": ParagraphStyle(
                "TableCell",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=cls.SLATE_700
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.white
            ),
            "meta_label": ParagraphStyle(
                "MetaLabel",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=cls.SLATE_500
            ),
            "meta_value": ParagraphStyle(
                "MetaValue",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                textColor=cls.SLATE_900
            ),
            "metric_value": ParagraphStyle(
                "MetricValue",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=16,
                textColor=cls.PRIMARY_DARK,
                alignment=1
            ),
            "metric_label": ParagraphStyle(
                "MetricLabel",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=cls.SLATE_500,
                alignment=1
            )
        }

    @classmethod
    def generate_report(
        cls,
        project: Project,
        competitors: List[Competitor],
        location_str: Optional[str] = None
    ) -> bytes:
        """
        Generates a PDF report summarizing competitor intelligence and benchmarking.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._get_styles()
        elements = []

        now_str = datetime.now(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

        # ── 1. Header Banner ──
        header_data = [
            [
                Paragraph("<b>LOCALLIFT</b> &bull; COMPETITOR BENCHMARKING", styles["meta_label"]),
                Paragraph(f"Report Date: {now_str}", ParagraphStyle("RightAlign", parent=styles["meta_label"], alignment=2))
            ],
            [
                Paragraph("Local Competitor Intelligence Report", styles["title"]),
                Paragraph(f"Target: <b>{project.name}</b>", ParagraphStyle("RightTarget", parent=styles["body_bold"], alignment=2))
            ]
        ]
        header_table = Table(header_data, colWidths=[360, 180])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 4))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=cls.PRIMARY, spaceAfter=10))

        # ── 2. Project Context Card ──
        ctx_data = [
            [
                Paragraph("<b>Business Name:</b>", styles["meta_label"]),
                Paragraph(project.name or "—", styles["meta_value"]),
                Paragraph("<b>Target Website:</b>", styles["meta_label"]),
                Paragraph(project.domain or "—", styles["meta_value"])
            ],
            [
                Paragraph("<b>Industry / Category:</b>", styles["meta_label"]),
                Paragraph(project.primary_category or "Local Business", styles["meta_value"]),
                Paragraph("<b>Target Location:</b>", styles["meta_label"]),
                Paragraph(location_str or "Configured Business Center", styles["meta_value"])
            ]
        ]
        ctx_table = Table(ctx_data, colWidths=[100, 170, 100, 170])
        ctx_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cls.SLATE_50),
            ("BOX", (0, 0), (-1, -1), 0.75, cls.SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(ctx_table)
        elements.append(Spacer(1, 12))

        # ── 3. Benchmarking Summary Metrics ──
        total_comps = len(competitors)
        valid_ratings = [c.rating for c in competitors if c.rating is not None]
        avg_rating = round(sum(valid_ratings) / len(valid_ratings), 1) if valid_ratings else None

        valid_reviews = [c.reviews_count for c in competitors if c.reviews_count]
        avg_reviews = round(sum(valid_reviews) / len(valid_reviews)) if valid_reviews else 0

        valid_ranks = [c.avg_maps_rank for c in competitors if c.avg_maps_rank is not None]
        avg_rank_val = round(sum(valid_ranks) / len(valid_ranks), 1) if valid_ranks else None

        geogrid_discovered_count = len([c for c in competitors if getattr(c, "source", "") in ("geogrid", "manual_and_geogrid")])

        metrics_data = [
            [
                Paragraph(str(total_comps), styles["metric_value"]),
                Paragraph(f"{avg_rating} ★" if avg_rating else "—", styles["metric_value"]),
                Paragraph(str(avg_reviews), styles["metric_value"]),
                Paragraph(f"#{avg_rank_val}" if avg_rank_val else "—", styles["metric_value"]),
                Paragraph(str(geogrid_discovered_count), styles["metric_value"]),
            ],
            [
                Paragraph("Tracked Competitors", styles["metric_label"]),
                Paragraph("Avg Google Rating", styles["metric_label"]),
                Paragraph("Avg Review Volume", styles["metric_label"]),
                Paragraph("Avg Local Rank", styles["metric_label"]),
                Paragraph("Geo-Grid Discovered", styles["metric_label"]),
            ]
        ]
        metrics_table = Table(metrics_data, colWidths=[108, 108, 108, 108, 108])
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cls.PRIMARY_LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, cls.PRIMARY),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("TOPPADDING", (0, 0), (-1, 0), 6),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 6),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 14))

        # ── 4. Competitor Table ──
        elements.append(Paragraph("Tracked Competitor Comparison", styles["section_heading"]))

        if not competitors:
            elements.append(Paragraph("No competitors currently configured or discovered for this project.", styles["body"]))
        else:
            table_rows = [
                [
                    Paragraph("Competitor Name", styles["table_header"]),
                    Paragraph("Domain / Website", styles["table_header"]),
                    Paragraph("Source", styles["table_header"]),
                    Paragraph("Rating & Reviews", styles["table_header"]),
                    Paragraph("Avg Rank", styles["table_header"]),
                    Paragraph("Best / Worst", styles["table_header"]),
                    Paragraph("Grid App.", styles["table_header"])
                ]
            ]

            for comp in competitors:
                src_label = getattr(comp, "source", "manual")
                if src_label == "manual_and_geogrid":
                    src_display = "Manual + Grid"
                elif src_label == "geogrid":
                    src_display = "Geo-Grid"
                else:
                    src_display = "Manual"

                rating_str = f"{comp.rating} ★" if comp.rating is not None else "—"
                rev_count = comp.reviews_count or 0
                rating_rev_str = f"{rating_str} ({rev_count})"

                avg_rk = f"#{comp.avg_maps_rank:.1f}" if comp.avg_maps_rank is not None else "—"
                best_rk = f"#{comp.best_rank}" if getattr(comp, "best_rank", None) is not None else "—"
                worst_rk = f"#{comp.worst_rank}" if getattr(comp, "worst_rank", None) is not None else "—"
                best_worst = f"{best_rk} / {worst_rk}"
                grid_app = str(getattr(comp, "grid_appearances", 0) or 0)

                domain_str = comp.domain or (getattr(comp, "website", "") or "—")

                table_rows.append([
                    Paragraph(f"<b>{comp.name}</b>", styles["table_cell"]),
                    Paragraph(domain_str, styles["table_cell"]),
                    Paragraph(src_display, styles["table_cell"]),
                    Paragraph(rating_rev_str, styles["table_cell"]),
                    Paragraph(avg_rk, styles["table_cell"]),
                    Paragraph(best_worst, styles["table_cell"]),
                    Paragraph(grid_app, styles["table_cell"])
                ])

            comp_table = Table(table_rows, colWidths=[130, 110, 65, 80, 50, 60, 45])
            comp_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY_DARK),
                ("BOX", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.SLATE_50]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(comp_table)

        elements.append(Spacer(1, 14))

        # ── 5. Methodological & Provenance Notes ──
        notes = [
            Paragraph("<b>Data Provenance & Methodology:</b>", styles["meta_label"]),
            Paragraph(
                "Competitor intelligence combines explicit manual targets with real-time local search and Geo-Grid visibility data. "
                "Rank positions reflect local organic pack positions observed across evaluated grid coordinates. "
                "Ratings and review volumes reflect live public Google listings.",
                styles["body"]
            )
        ]
        elements.append(KeepTogether(notes))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
