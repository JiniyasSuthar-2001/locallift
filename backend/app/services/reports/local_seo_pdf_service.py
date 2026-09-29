"""
LocalLift — Dedicated Local SEO Intelligence & Audit PDF Generator

Consumes the exact resolved report dataset from ReportSnapshotService and renders
a complete, multi-page, executive & technical PDF document with all row-level data.
"""

import io
from typing import Dict, Any, List
from datetime import datetime

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
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Adds running headers, footers, and dynamic page numbering."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(36, 762, "LocalLift — Local SEO Intelligence & Audit Report")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)

        # Running Footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)

        gen_text = f"Report Date: {datetime.now().strftime('%d %b %Y')}"
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawString(36, 30, gen_text)
        self.drawRightString(576, 30, page_text)
        self.drawCentredString(306, 30, "Confidential — Prepared for Client Deliverable")

        self.restoreState()


class LocalSEOPDFService:
    # Palette
    PRIMARY = colors.HexColor("#0F172A")       # Slate 900
    ACCENT = colors.HexColor("#059669")        # Emerald 600
    ACCENT_DARK = colors.HexColor("#047857")   # Emerald 700
    ACCENT_LIGHT = colors.HexColor("#ECFDF5")  # Emerald 50
    SLATE_800 = colors.HexColor("#1E293B")
    SLATE_600 = colors.HexColor("#475569")
    SLATE_400 = colors.HexColor("#94A3B8")
    SLATE_200 = colors.HexColor("#E2E8F0")
    SLATE_100 = colors.HexColor("#F1F5F9")
    SLATE_50 = colors.HexColor("#F8FAFC")
    WHITE = colors.HexColor("#FFFFFF")
    CRITICAL_RED = colors.HexColor("#DC2626")
    WARNING_AMBER = colors.HexColor("#D97706")
    PASS_GREEN = colors.HexColor("#16A34A")

    @classmethod
    def _get_styles(cls) -> Dict[str, ParagraphStyle]:
        sample = getSampleStyleSheet()
        return {
            "doc_title": ParagraphStyle(
                "DocTitle",
                parent=sample["Heading1"],
                fontName="Helvetica-Bold",
                fontSize=20,
                leading=24,
                textColor=cls.PRIMARY,
                spaceAfter=4
            ),
            "doc_subtitle": ParagraphStyle(
                "DocSubtitle",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=9.5,
                leading=13,
                textColor=cls.SLATE_600,
                spaceAfter=12
            ),
            "section_heading": ParagraphStyle(
                "SectionHeading",
                parent=sample["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=13,
                leading=16,
                textColor=cls.ACCENT_DARK,
                spaceBefore=14,
                spaceAfter=6,
                keepWithNext=True
            ),
            "sub_heading": ParagraphStyle(
                "SubHeading",
                parent=sample["Heading3"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                textColor=cls.SLATE_800,
                spaceBefore=8,
                spaceAfter=4,
                keepWithNext=True
            ),
            "body": ParagraphStyle(
                "BodyText",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=cls.SLATE_800
            ),
            "body_bold": ParagraphStyle(
                "BodyBold",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=12,
                textColor=cls.SLATE_800
            ),
            "small": ParagraphStyle(
                "SmallText",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=cls.SLATE_600
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=cls.WHITE
            ),
            "table_cell": ParagraphStyle(
                "TableCell",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10,
                textColor=cls.SLATE_800
            ),
            "table_cell_bold": ParagraphStyle(
                "TableCellBold",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=10,
                textColor=cls.SLATE_800
            ),
            "badge_pass": ParagraphStyle(
                "BadgePass",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7,
                leading=9,
                textColor=cls.PASS_GREEN
            ),
            "badge_fail": ParagraphStyle(
                "BadgeFail",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7,
                leading=9,
                textColor=cls.CRITICAL_RED
            ),
            "badge_warn": ParagraphStyle(
                "BadgeWarn",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7,
                leading=9,
                textColor=cls.WARNING_AMBER
            )
        }

    @classmethod
    def generate_pdf(cls, report_data: Dict[str, Any]) -> bytes:
        """
        Renders complete structured Local SEO Intelligence report into PDF bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=46,
            bottomMargin=50
        )

        styles = cls._get_styles()
        story = []

        bp = report_data.get("business_profile") or {}
        biz_name = bp.get("business_name") or "Local Business"
        health_score = report_data.get("health_score", 0)
        provenance = report_data.get("provenance") or {}
        coverage = report_data.get("coverage") or {}
        exec_summary = (report_data.get("executive_summary") or {}).get("narrative") or ""
        audit = report_data.get("audit") or {}
        geo = report_data.get("geo_visibility") or {}
        website_audit = report_data.get("website_audit") or {}
        keywords = report_data.get("keywords") or []
        reviews = (report_data.get("reputation") or {}).get("reviews") or []
        citations = (report_data.get("citations") or {}).get("listings") or []
        competitors = (report_data.get("competitors") or {}).get("items") or []
        action_plan = report_data.get("action_plan") or {}

        # =====================================================================
        # HEADER & PROVENANCE BANNER
        # =====================================================================
        story.append(Paragraph(f"Local SEO Intelligence & Audit Report", styles["doc_title"]))
        story.append(Paragraph(f"<b>Business Entity:</b> {biz_name} | <b>Domain:</b> {bp.get('website') or 'N/A'}", styles["doc_subtitle"]))

        # Metadata & Provenance Box
        gen_at = report_data.get("report_generated_at", "")[:19].replace("T", " ")
        data_as_of = report_data.get("data_as_of", "")[:19].replace("T", " ")
        central_id = (report_data.get("central_scan") or {}).get("id") or "None"
        overrides_cnt = (report_data.get("overrides_summary") or {}).get("total_overrides", 0)

        meta_table_data = [
            [
                Paragraph(f"<b>Report Generated:</b> {gen_at} UTC", styles["small"]),
                Paragraph(f"<b>Data Resolved As Of:</b> {data_as_of} UTC", styles["small"]),
                Paragraph(f"<b>Central Scan ID:</b> #{central_id}", styles["small"]),
                Paragraph(f"<b>Standalone Overrides:</b> {overrides_cnt} module(s)", styles["small"])
            ]
        ]
        meta_table = Table(meta_table_data, colWidths=[135, 135, 135, 135])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cls.SLATE_100),
            ('BOX', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # =====================================================================
        # EXECUTIVE SUMMARY & KPI CARDS
        # =====================================================================
        story.append(Paragraph("1. Executive Performance Summary", styles["section_heading"]))
        story.append(Paragraph(exec_summary, styles["body"]))
        story.append(Spacer(1, 8))

        # KPI Summary Grid
        kpi_data = [
            [
                Paragraph("<b>Health Score</b>", styles["small"]),
                Paragraph("<b>5x5 Geo-Grid Vis.</b>", styles["small"]),
                Paragraph("<b>Tracked Keywords</b>", styles["small"]),
                Paragraph("<b>Customer Reviews</b>", styles["small"]),
                Paragraph("<b>NAP Citations</b>", styles["small"])
            ],
            [
                Paragraph(f"<font size=14 color='#059669'><b>{health_score}/100</b></font>", styles["body"]),
                Paragraph(f"<font size=14 color='#059669'><b>{geo.get('local_visibility_pct', 0)}%</b></font>", styles["body"]),
                Paragraph(f"<font size=14 color='#0F172A'><b>{len(keywords)} terms</b></font>", styles["body"]),
                Paragraph(f"<font size=14 color='#0F172A'><b>{len(reviews)} ({bp.get('primary_phone') or 'Audited'})</b></font>", styles["body"]),
                Paragraph(f"<font size=14 color='#0F172A'><b>{len(citations)} citations</b></font>", styles["body"])
            ]
        ]
        kpi_table = Table(kpi_data, colWidths=[108, 108, 108, 108, 108])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cls.ACCENT_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, cls.ACCENT),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 12))

        # =====================================================================
        # 20 LOCAL SEO AUDIT CATEGORIES BREAKDOWN
        # =====================================================================
        cat_breakdowns = audit.get("category_breakdowns") or []
        prov_la = provenance.get("local_audit", {})
        story.append(Paragraph(f"2. Local SEO 20-Category Audit Framework <font size=8 color='#64748B'>(Source: {prov_la.get('source_type', 'Local Audit')}, Run #{prov_la.get('source_run_id', 'N/A')})</font>", styles["section_heading"]))
        
        cat_table_data = [
            [
                Paragraph("<b>Category Name</b>", styles["table_header"]),
                Paragraph("<b>Score</b>", styles["table_header"]),
                Paragraph("<b>Weight</b>", styles["table_header"]),
                Paragraph("<b>Passed</b>", styles["table_header"]),
                Paragraph("<b>Warnings</b>", styles["table_header"]),
                Paragraph("<b>Failed</b>", styles["table_header"]),
                Paragraph("<b>Not Verified</b>", styles["table_header"])
            ]
        ]
        for cb in cat_breakdowns:
            score_val = f"{cb.get('score')}/100" if cb.get("score") is not None else "N/A"
            cat_table_data.append([
                Paragraph(f"<b>{cb.get('category_name')}</b>", styles["table_cell"]),
                Paragraph(score_val, styles["table_cell_bold"]),
                Paragraph(f"{int(cb.get('weight', 0) * 100)}%", styles["table_cell"]),
                Paragraph(str(cb.get("passed_checks", 0)), styles["table_cell"]),
                Paragraph(str(cb.get("warning_checks", 0)), styles["table_cell"]),
                Paragraph(str(cb.get("failed_checks", 0)), styles["table_cell"]),
                Paragraph(str(cb.get("not_verified_checks", 0)), styles["table_cell"]),
            ])

        cat_table = Table(cat_table_data, colWidths=[180, 60, 50, 60, 60, 60, 70], repeatRows=1)
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 14))

        # =====================================================================
        # COMPLETE LOCAL SEO AUDIT FINDINGS (ALL ROWS)
        # =====================================================================
        findings = audit.get("findings") or []
        story.append(Paragraph(f"3. Complete Local SEO Audit Findings ({len(findings)} checkpoints evaluated)", styles["section_heading"]))
        story.append(Paragraph("Complete row-level findings including category, checkpoint title, status, severity, and actionable recommendation.", styles["small"]))
        story.append(Spacer(1, 4))

        findings_table_data = [
            [
                Paragraph("<b>Category</b>", styles["table_header"]),
                Paragraph("<b>Checkpoint Title</b>", styles["table_header"]),
                Paragraph("<b>Status</b>", styles["table_header"]),
                Paragraph("<b>Severity</b>", styles["table_header"]),
                Paragraph("<b>Evidence & Recommendation</b>", styles["table_header"])
            ]
        ]

        for f in findings:
            st = (f.get("status") or "").upper()
            if st == "PASS":
                status_p = Paragraph("PASS", styles["badge_pass"])
            elif st in ("FAIL", "CRITICAL"):
                status_p = Paragraph("FAIL", styles["badge_fail"])
            else:
                status_p = Paragraph(st or "WARN", styles["badge_warn"])

            ev_rec = f"<b>Evidence:</b> {f.get('evidence') or 'Verified'}<br/><b>Recommendation:</b> {f.get('recommended_action') or f.get('recommendation') or 'Maintain standards.'}"
            findings_table_data.append([
                Paragraph(f.get("category_name", ""), styles["table_cell_bold"]),
                Paragraph(f.get("title", ""), styles["table_cell"]),
                status_p,
                Paragraph(f.get("severity", "INFO"), styles["table_cell"]),
                Paragraph(ev_rec, styles["table_cell"])
            ])

        findings_table = Table(findings_table_data, colWidths=[100, 130, 45, 45, 220], repeatRows=1)
        findings_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
        ]))
        story.append(findings_table)
        story.append(Spacer(1, 14))

        # =====================================================================
        # GEO-GRID 5x5 SCAN MATRIX & ALL POINTS
        # =====================================================================
        prov_geo = provenance.get("geo", {})
        pts = geo.get("points") or []
        story.append(Paragraph(f"4. 5x5 Geo-Grid Rankings ({len(pts)} Geographic Coordinate Pins)", styles["section_heading"]))
        story.append(Paragraph(
            f"<b>Keyword:</b> {geo.get('keyword') or 'Local Search'} | <b>Grid Size:</b> {geo.get('grid_size', 5)}x{geo.get('grid_size', 5)} | "
            f"<b>Radius:</b> {geo.get('radius_km', 10)} km | <b>Local Visibility:</b> {geo.get('local_visibility_pct', 0)}% | "
            f"<b>Average Rank:</b> {geo.get('average_rank') or 'N/A'} (Source: {prov_geo.get('source_type', 'Geo-Grid')}, Scan #{prov_geo.get('source_run_id', 'N/A')})",
            styles["body"]
        ))
        story.append(Spacer(1, 4))

        geo_table_data = [
            [
                Paragraph("<b>#</b>", styles["table_header"]),
                Paragraph("<b>Area Name</b>", styles["table_header"]),
                Paragraph("<b>Lat, Lng</b>", styles["table_header"]),
                Paragraph("<b>Rank</b>", styles["table_header"]),
                Paragraph("<b>Status</b>", styles["table_header"]),
                Paragraph("<b>Matched Business / Domain</b>", styles["table_header"]),
                Paragraph("<b>Distance</b>", styles["table_header"])
            ]
        ]

        for p in pts:
            rank_display = str(p.get("rank")) if p.get("rank") is not None else "20+"
            lat_val = f"{p.get('latitude', 0.0):.4f}" if p.get("latitude") is not None else "—"
            lng_val = f"{p.get('longitude', 0.0):.4f}" if p.get("longitude") is not None else "—"
            dist_val = f"{p.get('distance_km'):.1f} km" if p.get("distance_km") is not None else "—"
            dir_val = f" {p.get('direction')}" if p.get("direction") else ""
            geo_table_data.append([
                Paragraph(str(p.get("point_number", 0) + 1), styles["table_cell_bold"]),
                Paragraph(p.get("area_name", ""), styles["table_cell"]),
                Paragraph(f"{lat_val}, {lng_val}", styles["table_cell"]),
                Paragraph(f"<b>{rank_display}</b>", styles["table_cell_bold"]),
                Paragraph(p.get("status", ""), styles["table_cell"]),
                Paragraph(p.get("matched_business") or p.get("matched_domain") or "Not in top pack", styles["table_cell"]),
                Paragraph(f"{dist_val}{dir_val}", styles["table_cell"])
            ])

        geo_table = Table(geo_table_data, colWidths=[25, 125, 90, 40, 60, 140, 60], repeatRows=1)
        geo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 3),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
        ]))
        story.append(geo_table)
        story.append(Spacer(1, 14))

        # Geo-Grid Competitors
        geo_comps = geo.get("competitors") or []
        if geo_comps:
            story.append(Paragraph(f"Geo-Grid Competitor Intelligence ({len(geo_comps)} competitor ranking pins recorded)", styles["sub_heading"]))
            geo_comp_data = [
                [
                    Paragraph("<b>Pin Area</b>", styles["table_header"]),
                    Paragraph("<b>Competitor Name</b>", styles["table_header"]),
                    Paragraph("<b>Rank</b>", styles["table_header"]),
                    Paragraph("<b>Domain</b>", styles["table_header"]),
                    Paragraph("<b>Distance</b>", styles["table_header"])
                ]
            ]
            for gc in geo_comps[:40]:  # Up to 40 competitor observations in PDF table
                dist_str = f"{gc.get('distance_km'):.1f} km" if gc.get("distance_km") is not None else "N/A"
                geo_comp_data.append([
                    Paragraph(gc.get("area_name", ""), styles["table_cell"]),
                    Paragraph(f"<b>{gc.get('competitor_name', '')}</b>", styles["table_cell_bold"]),
                    Paragraph(str(gc.get("rank") or "N/A"), styles["table_cell"]),
                    Paragraph(gc.get("domain") or "N/A", styles["table_cell"]),
                    Paragraph(dist_str, styles["table_cell"])
                ])
            geo_comp_table = Table(geo_comp_data, colWidths=[120, 160, 40, 140, 80], repeatRows=1)
            geo_comp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
                ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ('PADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
            ]))
            story.append(geo_comp_table)
            story.append(Spacer(1, 14))

        # =====================================================================
        # TECHNICAL WEBSITE AUDIT & ANALYZED PAGES
        # =====================================================================
        pages = website_audit.get("pages") or []
        issues = website_audit.get("issues") or []
        story.append(Paragraph(f"5. Technical Website Crawl & On-Page Audit ({len(pages)} pages analyzed)", styles["section_heading"]))
        
        psi = website_audit.get("pagespeed") or {}
        if psi:
            story.append(Paragraph(
                f"<b>Google PageSpeed Insights:</b> Mobile Score {psi.get('performance_score') or 'N/A'}/100 | "
                f"FCP: {psi.get('fcp') or 'N/A'} | LCP: {psi.get('lcp') or 'N/A'} | CLS: {psi.get('cls') or 'N/A'}",
                styles["body"]
            ))
            story.append(Spacer(1, 4))

        if pages:
            pages_table_data = [
                [
                    Paragraph("<b>Page URL</b>", styles["table_header"]),
                    Paragraph("<b>HTTP</b>", styles["table_header"]),
                    Paragraph("<b>H1 Heading</b>", styles["table_header"]),
                    Paragraph("<b>Words</b>", styles["table_header"]),
                    Paragraph("<b>Speed</b>", styles["table_header"]),
                    Paragraph("<b>Schema</b>", styles["table_header"])
                ]
            ]
            for p in pages:
                pages_table_data.append([
                    Paragraph(p.get("url", ""), styles["table_cell"]),
                    Paragraph(str(p.get("status_code", 200)), styles["table_cell"]),
                    Paragraph((p.get("h1") or "Missing H1")[:40], styles["table_cell"]),
                    Paragraph(str(p.get("word_count", 0)), styles["table_cell"]),
                    Paragraph(f"{p.get('load_time_ms', 0)}ms", styles["table_cell"]),
                    Paragraph(", ".join(p.get("schema_types", [])[:2]) or "None", styles["table_cell"])
                ])
            pages_table = Table(pages_table_data, colWidths=[180, 40, 140, 45, 45, 90], repeatRows=1)
            pages_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
                ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ('PADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
            ]))
            story.append(pages_table)
            story.append(Spacer(1, 14))

        # =====================================================================
        # TRACKED KEYWORDS & SERP POSITIONS
        # =====================================================================
        if keywords:
            story.append(Paragraph(f"6. Local Keyword Rankings ({len(keywords)} terms)", styles["section_heading"]))
            kw_table_data = [
                [
                    Paragraph("<b>Keyword Term</b>", styles["table_header"]),
                    Paragraph("<b>Target Location</b>", styles["table_header"]),
                    Paragraph("<b>Current</b>", styles["table_header"]),
                    Paragraph("<b>Previous</b>", styles["table_header"]),
                    Paragraph("<b>SERP Type</b>", styles["table_header"]),
                    Paragraph("<b>Relevance</b>", styles["table_header"])
                ]
            ]
            for k in keywords:
                curr = str(k.get("current_rank")) if k.get("current_rank") else "Unranked"
                prev = str(k.get("previous_rank")) if k.get("previous_rank") else "-"
                kw_table_data.append([
                    Paragraph(f"<b>{k.get('keyword', '')}</b>", styles["table_cell_bold"]),
                    Paragraph(k.get("target_location") or "Local Area", styles["table_cell"]),
                    Paragraph(curr, styles["table_cell_bold"]),
                    Paragraph(prev, styles["table_cell"]),
                    Paragraph(k.get("serp_type", "Local Pack"), styles["table_cell"]),
                    Paragraph(k.get("business_relevance", "High"), styles["table_cell"])
                ])
            kw_table = Table(kw_table_data, colWidths=[180, 120, 55, 55, 70, 60], repeatRows=1)
            kw_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
                ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ('PADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
            ]))
            story.append(kw_table)
            story.append(Spacer(1, 14))

        # =====================================================================
        # CUSTOMER REVIEWS & CITATIONS
        # =====================================================================
        if reviews or citations:
            story.append(Paragraph(f"7. Reputation & Directory Citations", styles["section_heading"]))
            
            if reviews:
                story.append(Paragraph(f"Customer Reviews ({len(reviews)} records recorded)", styles["sub_heading"]))
                rev_table_data = [
                    [
                        Paragraph("<b>Author</b>", styles["table_header"]),
                        Paragraph("<b>Rating</b>", styles["table_header"]),
                        Paragraph("<b>Review Text</b>", styles["table_header"]),
                        Paragraph("<b>Response Status</b>", styles["table_header"]),
                        Paragraph("<b>Date</b>", styles["table_header"])
                    ]
                ]
                for r in reviews:
                    rev_table_data.append([
                        Paragraph(r.get("author_name", "Customer"), styles["table_cell_bold"]),
                        Paragraph(f"{r.get('rating', 5)} ★", styles["table_cell_bold"]),
                        Paragraph((r.get("review_text") or "No text comment.")[:100], styles["table_cell"]),
                        Paragraph(r.get("response_status", "unanswered"), styles["table_cell"]),
                        Paragraph(r.get("review_date", "")[:10], styles["table_cell"])
                    ])
                rev_table = Table(rev_table_data, colWidths=[100, 45, 235, 90, 70], repeatRows=1)
                rev_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
                    ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                    ('PADDING', (0, 0), (-1, -1), 3),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
                ]))
                story.append(rev_table)
                story.append(Spacer(1, 10))

            if citations:
                story.append(Paragraph(f"Directory Citations ({len(citations)} listings audited)", styles["sub_heading"]))
                cit_table_data = [
                    [
                        Paragraph("<b>Directory Source</b>", styles["table_header"]),
                        Paragraph("<b>Domain</b>", styles["table_header"]),
                        Paragraph("<b>NAP Status</b>", styles["table_header"]),
                        Paragraph("<b>Verification</b>", styles["table_header"]),
                        Paragraph("<b>Listing URL</b>", styles["table_header"])
                    ]
                ]
                for c in citations:
                    cit_table_data.append([
                        Paragraph(c.get("directory_name", ""), styles["table_cell_bold"]),
                        Paragraph(c.get("domain", ""), styles["table_cell"]),
                        Paragraph(c.get("nap_status", ""), styles["table_cell"]),
                        Paragraph(c.get("verification_status", ""), styles["table_cell"]),
                        Paragraph((c.get("listing_url") or "Listed")[:45], styles["table_cell"])
                    ])
                cit_table = Table(cit_table_data, colWidths=[120, 100, 80, 80, 160], repeatRows=1)
                cit_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
                    ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                    ('PADDING', (0, 0), (-1, -1), 3),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
                ]))
                story.append(cit_table)
                story.append(Spacer(1, 14))

        # =====================================================================
        # 90-DAY STRATEGIC ACTION ROADMAP
        # =====================================================================
        story.append(Paragraph("8. 90-Day Local SEO Strategic Roadmap", styles["section_heading"]))
        
        roadmap_data = [
            [
                Paragraph("<b>Month 1: Foundation & Critical Fixes</b>", styles["table_header"]),
                Paragraph("<b>Month 2: On-Page & Suburban Pages</b>", styles["table_header"]),
                Paragraph("<b>Month 3: Authority & Geo Velocity</b>", styles["table_header"])
            ]
        ]
        m1_actions = "<br/>• ".join([""] + (action_plan.get("month_1", {}).get("actions", [])))
        m2_actions = "<br/>• ".join([""] + (action_plan.get("month_2", {}).get("actions", [])))
        m3_actions = "<br/>• ".join([""] + (action_plan.get("month_3", {}).get("actions", [])))

        roadmap_data.append([
            Paragraph(m1_actions or "• Standardize canonical NAP.<br/>• Fix high-severity crawl errors.", styles["table_cell"]),
            Paragraph(m2_actions or "• Deploy LocalBusiness Schema.<br/>• Optimize suburb landing pages.", styles["table_cell"]),
            Paragraph(m3_actions or "• Scale review acquisition.<br/>• Acquire regional citations.", styles["table_cell"])
        ])

        roadmap_table = Table(roadmap_data, colWidths=[180, 180, 180])
        roadmap_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.ACCENT_DARK),
            ('BACKGROUND', (0, 1), (-1, 1), cls.ACCENT_LIGHT),
            ('BOX', (0, 0), (-1, -1), 1, cls.ACCENT_DARK),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(roadmap_table)
        story.append(Spacer(1, 14))

        # =====================================================================
        # PROVENANCE & METHODOLOGY LEGEND
        # =====================================================================
        story.append(Paragraph("9. Audit Provenance & Methodology", styles["section_heading"]))
        prov_legend = report_data.get("methodology") or {}
        prov_data = [
            [Paragraph("<b>Classification</b>", styles["table_header"]), Paragraph("<b>Methodology & Evidence Guarantee</b>", styles["table_header"])]
        ]
        for k, v in prov_legend.items():
            prov_data.append([
                Paragraph(f"<b>{k}</b>", styles["table_cell_bold"]),
                Paragraph(v, styles["table_cell"])
            ])
        prov_table = Table(prov_data, colWidths=[120, 420])
        prov_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), cls.PRIMARY),
            ('GRID', (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [cls.WHITE, cls.SLATE_50])
        ]))
        story.append(prov_table)

        # Build PDF
        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
