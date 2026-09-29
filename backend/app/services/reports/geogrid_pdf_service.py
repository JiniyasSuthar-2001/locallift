import io
import math
from typing import Dict, Any, List, Optional, Tuple
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
from reportlab.graphics.shapes import Drawing, Rect, Circle, String, Group, Line


class GeoGridPDFService:
    """
    Production-grade ReportLab PDF generation service for LocalLift Geo-Grid.
    Generates:
    1. Single Full Scan PDF (with real map, summary metrics, all points, competitor intelligence, methodology).
    2. Current + Previous 2 Scans Comparison PDF (multi-scan trend, max 3 scans).
    3. Selected Grid Point PDF (deep-dive analysis for an individual point).
    """

    # Brand Palette
    PRIMARY = colors.HexColor("#236B4F")        # LocalLift Forest Green
    PRIMARY_DARK = colors.HexColor("#142820")   # Dark Forest
    PRIMARY_LIGHT = colors.HexColor("#E8F2EC")  # Soft Mint
    ACCENT_BLUE = colors.HexColor("#2563EB")    # Blue
    ACCENT_AMBER = colors.HexColor("#D97706")   # Amber
    ACCENT_ROSE = colors.HexColor("#E11D48")    # Rose
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
                textColor=cls.SLATE_700,
                spaceAfter=10
            ),
            "heading2": ParagraphStyle(
                "Heading2",
                parent=sample["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                textColor=cls.PRIMARY,
                spaceBefore=12,
                spaceAfter=6
            ),
            "heading3": ParagraphStyle(
                "Heading3",
                parent=sample["Heading3"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                textColor=cls.SLATE_900,
                spaceBefore=8,
                spaceAfter=4
            ),
            "body": ParagraphStyle(
                "Body",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=cls.SLATE_700
            ),
            "body_bold": ParagraphStyle(
                "BodyBold",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=12,
                textColor=cls.SLATE_900
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=9.5,
                textColor=colors.white
            ),
            "table_cell": ParagraphStyle(
                "TableCell",
                parent=sample["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=9.5,
                textColor=cls.SLATE_900
            ),
            "table_cell_bold": ParagraphStyle(
                "TableCellBold",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=9.5,
                textColor=cls.SLATE_900
            ),
            "meta_label": ParagraphStyle(
                "MetaLabel",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=7.5,
                leading=9.5,
                textColor=cls.SLATE_500
            ),
            "meta_val": ParagraphStyle(
                "MetaVal",
                parent=sample["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                textColor=cls.PRIMARY_DARK
            )
        }

    @classmethod
    def _create_map_drawing(
        cls,
        grid_size: int,
        points: List[Dict[str, Any]],
        center_name: str = "Business Center"
    ) -> Drawing:
        """
        Renders a proportional geographic map canvas for the report.
        Draws center marker, perimeter scan radius, and color-coded rank pins for 9, 25, or 49 points.
        """
        canvas_width = 540
        canvas_height = 200
        d = Drawing(canvas_width, canvas_height)

        # Background card
        d.add(Rect(0, 0, canvas_width, canvas_height, fillColor=cls.SLATE_50, strokeColor=cls.SLATE_200, strokeWidth=1, rx=8, ry=8))

        if not points:
            d.add(String(200, 100, "No GPS grid points available.", fontName="Helvetica", fontSize=10, fillColor=cls.SLATE_500))
            return d

        # Calculate coordinate bounds
        lats = [float(p.get("lat") or p.get("latitude") or 0.0) for p in points if (p.get("lat") or p.get("latitude"))]
        lngs = [float(p.get("lng") or p.get("longitude") or 0.0) for p in points if (p.get("lng") or p.get("longitude"))]

        min_lat = min(lats) if lats else 0
        max_lat = max(lats) if lats else 1
        min_lng = min(lngs) if lngs else 0
        max_lng = max(lngs) if lngs else 1

        lat_range = max_lat - min_lat or 0.01
        lng_range = max_lng - min_lng or 0.01

        map_w = 400
        map_h = 160
        origin_x = 70
        origin_y = 20

        # Scan Radius Circle
        center_x = origin_x + (map_w / 2)
        center_y = origin_y + (map_h / 2)
        radius_px = min(map_w, map_h) * 0.46
        d.add(Circle(center_x, center_y, radius_px, fillColor=cls.PRIMARY_LIGHT, strokeColor=cls.PRIMARY, strokeWidth=1, strokeDashArray=[3, 3]))

        # Grid guidelines
        for i in range(1, grid_size):
            frac = i / float(grid_size)
            gx = origin_x + (frac * map_w)
            gy = origin_y + (frac * map_h)
            d.add(Line(gx, origin_y + 10, gx, origin_y + map_h - 10, strokeColor=cls.SLATE_200, strokeWidth=0.5))
            d.add(Line(origin_x + 10, gy, origin_x + map_w - 10, gy, strokeColor=cls.SLATE_200, strokeWidth=0.5))

        # Center Pin
        d.add(Circle(center_x, center_y, 7, fillColor=cls.PRIMARY, strokeColor=colors.white, strokeWidth=1.5))
        d.add(String(center_x - 14, center_y - 14, "CENTER", fontName="Helvetica-Bold", fontSize=6, fillColor=cls.PRIMARY))

        # Points
        for pt in points:
            p_lat = float(pt.get("lat") or pt.get("latitude") or 0.0)
            p_lng = float(pt.get("lng") or pt.get("longitude") or 0.0)
            rank = pt.get("rank")
            status = str(pt.get("status") or "").upper()
            pt_num = pt.get("point_number", 0)

            # Map coordinates to pixel canvas
            px = origin_x + (((p_lng - min_lng) / lng_range) * (map_w - 30)) + 15
            py = origin_y + (((p_lat - min_lat) / lat_range) * (map_h - 30)) + 15

            # Pin Color
            if status in ["PROVIDER_ERROR", "ERROR", "TIMEOUT"]:
                fill_c = cls.SLATE_500
                txt = "ERR" if status != "TIMEOUT" else "TO"
            elif status == "NOT_FOUND" or (rank is None):
                fill_c = cls.ACCENT_ROSE
                txt = "NF"
            elif rank <= 3:
                fill_c = cls.PRIMARY
                txt = f"#{rank}"
            elif rank <= 7:
                fill_c = cls.ACCENT_BLUE
                txt = f"#{rank}"
            elif rank <= 15:
                fill_c = cls.ACCENT_AMBER
                txt = f"#{rank}"
            else:
                fill_c = cls.ACCENT_ROSE
                txt = f"#{rank}"

            # Marker Box
            box_size = 14 if grid_size <= 5 else 11
            d.add(Rect(px - (box_size / 2), py - (box_size / 2), box_size, box_size, fillColor=fill_c, strokeColor=colors.white, strokeWidth=1, rx=2, ry=2))
            d.add(String(px - 4, py - 3, txt[:3], fontName="Helvetica-Bold", fontSize=5 if grid_size > 5 else 6, fillColor=colors.white))

        return d

    @classmethod
    def generate_single_scan_pdf(
        cls,
        project: Any,
        scan: Any,
        points: List[Any],
        organization_name: str = "LocalLift Organization"
    ) -> bytes:
        """
        Generates a comprehensive PDF for a single complete/historical scan.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._get_styles()
        story = []

        # 1. Header Banner
        grid_dim = f"{scan.grid_size}×{scan.grid_size}"
        total_pts = scan.grid_size * scan.grid_size
        scanned_date_str = scan.started_at.strftime("%d %b %Y, %I:%M %p") if scan.started_at else "N/A"

        story.append(Paragraph(f"Geo-Grid Local Visibility Report — {project.name}", styles["title"]))
        story.append(Paragraph(
            f"<b>Keyword:</b> {scan.keyword_rel.keyword if getattr(scan, 'keyword_rel', None) else (scan.keyword or 'Target Keyword')} &nbsp;|&nbsp; "
            f"<b>Grid:</b> {grid_dim} ({total_pts} Points) &nbsp;|&nbsp; "
            f"<b>Radius:</b> {scan.radius_km} km &nbsp;|&nbsp; "
            f"<b>Scanned:</b> {scanned_date_str}",
            styles["subtitle"]
        ))
        story.append(HRFlowable(width="100%", thickness=1.5, color=cls.PRIMARY, spaceBefore=2, spaceAfter=8))

        # Status warning if not completed
        if scan.scan_status in ["running", "queued"]:
            story.append(Paragraph(f"<b>Notice:</b> This scan is currently in progress ({scan.scan_status}). Partial snapshot shown below.", styles["body_bold"]))
            story.append(Spacer(1, 6))
        elif scan.scan_status == "failed":
            story.append(Paragraph(f"<b>Warning:</b> This scan failed: {scan.cancellation_reason or 'Provider communication failure'}.", styles["body_bold"]))
            story.append(Spacer(1, 6))

        # 2. Executive Metrics Summary Table
        ranked_pts = [p for p in points if getattr(p, "rank", None) is not None]
        best_rank = min([p.rank for p in ranked_pts]) if ranked_pts else "N/A"
        worst_rank = max([p.rank for p in ranked_pts]) if ranked_pts else "N/A"

        summary_data = [
            [
                Paragraph("TOTAL POINTS", styles["meta_label"]),
                Paragraph("COMPLETED", styles["meta_label"]),
                Paragraph("RANKED IN PACK", styles["meta_label"]),
                Paragraph("NOT FOUND", styles["meta_label"]),
                Paragraph("ERRORS / TO", styles["meta_label"]),
                Paragraph("AVG RANK", styles["meta_label"]),
                Paragraph("VISIBILITY %", styles["meta_label"])
            ],
            [
                Paragraph(str(scan.total_points or total_pts), styles["meta_val"]),
                Paragraph(str(scan.completed_points or len(points)), styles["meta_val"]),
                Paragraph(str(scan.ranking_found_points or len(ranked_pts)), styles["meta_val"]),
                Paragraph(str(scan.not_found_points or 0), styles["meta_val"]),
                Paragraph(str((scan.provider_error_points or 0) + (scan.timeout_points or 0)), styles["meta_val"]),
                Paragraph(f"#{scan.average_rank:.1f}" if scan.average_rank else "N/A", styles["meta_val"]),
                Paragraph(f"{scan.local_visibility_pct:.0f}%" if scan.local_visibility_pct is not None else "0%", styles["meta_val"])
            ]
        ]
        t_summary = Table(summary_data, colWidths=[75, 75, 80, 75, 75, 75, 80])
        t_summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cls.SLATE_50),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 10))

        # 3. Geographic Grid Map
        story.append(Paragraph("Geographic Grid Positioning Map", styles["heading2"]))
        dict_points = [
            {
                "point_number": getattr(p, "point_number", 0),
                "row": getattr(p, "row", 0),
                "col": getattr(p, "col", 0),
                "lat": getattr(p, "latitude", 0.0),
                "lng": getattr(p, "longitude", 0.0),
                "rank": getattr(p, "rank", None),
                "status": getattr(p, "status", "NOT_FOUND")
            }
            for p in points
        ]
        map_drawing = cls._create_map_drawing(scan.grid_size, dict_points, scan.center_name or "Business Center")
        story.append(map_drawing)
        story.append(Spacer(1, 6))

        # Map Legend
        legend_data = [[
            Paragraph("<b>Legend:</b>", styles["body_bold"]),
            Paragraph("● <b>#1–3:</b> Top 3 Pack (Emerald)", styles["body"]),
            Paragraph("● <b>#4–7:</b> Page 1 (Blue)", styles["body"]),
            Paragraph("● <b>#8–15:</b> Moderate (Amber)", styles["body"]),
            Paragraph("● <b>#16+:</b> Low (Red)", styles["body"]),
            Paragraph("● <b>NF:</b> Not Found", styles["body"]),
            Paragraph("● <b>ERR:</b> Error/Timeout", styles["body"])
        ]]
        t_legend = Table(legend_data, colWidths=[50, 85, 80, 85, 75, 75, 85])
        t_legend.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t_legend)
        story.append(Spacer(1, 12))

        # 4. Discrete Grid Points Table
        story.append(Paragraph(f"Grid Coordinate Search Breakdown ({len(points)} Points)", styles["heading2"]))
        pt_headers = [
            Paragraph("Point", styles["table_header"]),
            Paragraph("Area / Locality", styles["table_header"]),
            Paragraph("GPS Coordinates", styles["table_header"]),
            Paragraph("Distance & Direction", styles["table_header"]),
            Paragraph("Rank", styles["table_header"]),
            Paragraph("Matched Business", styles["table_header"]),
            Paragraph("Status", styles["table_header"])
        ]
        pt_rows = [pt_headers]

        for p in sorted(points, key=lambda x: getattr(x, "point_number", 0)):
            r_val = getattr(p, "rank", None)
            st_val = (getattr(p, "status", "") or "").upper()
            rank_str = f"#{r_val}" if r_val else ("NF" if st_val == "NOT_FOUND" else st_val)
            dist_str = f"{getattr(p, 'distance_km', 0.0) or 0.0} km ({getattr(p, 'direction', 'Center') or 'Center'})"
            gps_str = f"{getattr(p, 'latitude', 0.0):.5f}, {getattr(p, 'longitude', 0.0):.5f}"
            area_str = str(getattr(p, "area_name", "") or "Area name unavailable")

            pt_rows.append([
                Paragraph(f"#{getattr(p, 'point_number', 0)}", styles["table_cell_bold"]),
                Paragraph(area_str[:22], styles["table_cell"]),
                Paragraph(gps_str, styles["table_cell"]),
                Paragraph(dist_str, styles["table_cell"]),
                Paragraph(rank_str, styles["table_cell_bold"]),
                Paragraph(str(getattr(p, "matched_business", "") or "—")[:25], styles["table_cell"]),
                Paragraph(st_val, styles["table_cell"])
            ])

        t_points = Table(pt_rows, colWidths=[35, 95, 95, 90, 40, 130, 55], repeatRows=1)
        t_points.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.SLATE_50]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_points)
        story.append(Spacer(1, 14))

        # 5. Competitor Intelligence Summary Across Scan
        competitor_agg: Dict[str, Dict[str, Any]] = {}
        for p in points:
            comp_list = getattr(p, "competitors", []) or []
            p_rank = getattr(p, "rank", None)
            for c in comp_list:
                name = c.get("title") or c.get("name")
                if not name or c.get("is_target"):
                    continue
                pos = c.get("position")
                if name not in competitor_agg:
                    competitor_agg[name] = {
                        "name": name,
                        "domain": c.get("domain", ""),
                        "category": c.get("category", ""),
                        "rating": c.get("rating"),
                        "reviews": c.get("reviews_count"),
                        "appearances": 0,
                        "ranks": [],
                        "points_above": 0,
                        "points_below": 0
                    }
                competitor_agg[name]["appearances"] += 1
                if pos:
                    competitor_agg[name]["ranks"].append(pos)
                    if p_rank:
                        if pos < p_rank:
                            competitor_agg[name]["points_above"] += 1
                        elif pos > p_rank:
                            competitor_agg[name]["points_below"] += 1

        if competitor_agg:
            story.append(KeepTogether([
                Paragraph("Top Competitors Detected Across Service Area", styles["heading2"]),
                Paragraph("Aggregate visibility across all discrete geographic search points.", styles["body"]),
                Spacer(1, 6)
            ]))

            comp_headers = [
                Paragraph("Competitor Name", styles["table_header"]),
                Paragraph("Category", styles["table_header"]),
                Paragraph("Rating & Reviews", styles["table_header"]),
                Paragraph("Appearances", styles["table_header"]),
                Paragraph("Best Rank", styles["table_header"]),
                Paragraph("Avg Rank", styles["table_header"]),
                Paragraph("Points Above You", styles["table_header"])
            ]
            comp_rows = [comp_headers]

            sorted_comps = sorted(competitor_agg.values(), key=lambda x: (x["points_above"], x["appearances"]), reverse=True)[:10]
            for sc in sorted_comps:
                best_r = min(sc["ranks"]) if sc["ranks"] else "—"
                avg_r = (sum(sc["ranks"]) / len(sc["ranks"])) if sc["ranks"] else 0.0
                rating_str = f"{sc['rating']}★ ({sc['reviews']})" if sc.get("rating") else "—"

                comp_rows.append([
                    Paragraph(sc["name"][:30], styles["table_cell_bold"]),
                    Paragraph(sc.get("category", "—")[:20] if sc.get("category") else "—", styles["table_cell"]),
                    Paragraph(rating_str, styles["table_cell"]),
                    Paragraph(f"{sc['appearances']}/{len(points)}", styles["table_cell"]),
                    Paragraph(f"#{best_r}" if best_r != "—" else "—", styles["table_cell"]),
                    Paragraph(f"#{avg_r:.1f}" if avg_r > 0 else "—", styles["table_cell"]),
                    Paragraph(str(sc["points_above"]), styles["table_cell_bold"])
                ])

            t_comp = Table(comp_rows, colWidths=[130, 85, 85, 65, 55, 55, 65])
            t_comp.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY_DARK),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
                ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.SLATE_50]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_comp)
            story.append(Spacer(1, 14))

        # 6. Methodology & Disclaimers
        story.append(KeepTogether([
            Paragraph("Scan Methodology & Integrity Disclaimers", styles["heading3"]),
            Paragraph(
                "• <b>Spatial Coordinate Modeling:</b> Search coordinates are computed using spherical geodesic Haversine displacement centered at your business location.<br/>"
                "• <b>Real-Time Observation:</b> Each point executes an independent localized query to observe Google Local Pack positions at that GPS coordinate.<br/>"
                "• <b>Evidence-Based Analysis:</b> All metrics, competitor ranks, and ratings reflect actual observed provider data without algorithm conjecture.<br/>"
                "• <b>Data Immutability:</b> Historical scan reports preserve the exact state observed at the time of execution and are never retrospectively modified.",
                styles["body"]
            ),
            Spacer(1, 10),
            Paragraph(f"Generated by LocalLift Local SEO Intelligence Platform · {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}", styles["meta_label"])
        ]))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def generate_multi_scan_comparison_pdf(
        cls,
        project: Any,
        scans_with_points: List[Tuple[Any, List[Any]]],
        organization_name: str = "LocalLift Organization"
    ) -> bytes:
        """
        Generates a chronological multi-scan report comparing up to 3 scans (Current + Previous 2).
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._get_styles()
        story = []

        # Chronological sorting (earliest to newest)
        scans_sorted = sorted(scans_with_points, key=lambda x: x[0].started_at if x[0].started_at else datetime.min)
        num_scans = len(scans_sorted)

        story.append(Paragraph(f"Geo-Grid Historical Multi-Scan Report — {project.name}", styles["title"]))
        story.append(Paragraph(
            f"Comparing <b>{num_scans} chronological scan{'s' if num_scans > 1 else ''}</b> for performance and local visibility trend tracking.",
            styles["subtitle"]
        ))
        story.append(HRFlowable(width="100%", thickness=1.5, color=cls.PRIMARY, spaceBefore=2, spaceAfter=10))

        # Comparison Overview Table
        comp_overview_headers = [
            Paragraph("Scan ID & Date", styles["table_header"]),
            Paragraph("Keyword", styles["table_header"]),
            Paragraph("Grid & Radius", styles["table_header"]),
            Paragraph("Total Pts", styles["table_header"]),
            Paragraph("Ranked Pts", styles["table_header"]),
            Paragraph("Avg Rank", styles["table_header"]),
            Paragraph("Visibility %", styles["table_header"])
        ]
        comp_overview_rows = [comp_overview_headers]

        for s, pts in scans_sorted:
            d_str = s.started_at.strftime("%d %b %Y, %I:%M %p") if s.started_at else "N/A"
            kw_str = s.keyword_rel.keyword if getattr(s, 'keyword_rel', None) else (s.keyword or "Target Keyword")
            dim_str = f"{s.grid_size}×{s.grid_size} ({s.radius_km} km)"
            ranked_cnt = s.ranking_found_points or len([p for p in pts if getattr(p, "rank", None) is not None])

            comp_overview_rows.append([
                Paragraph(f"<b>#{s.id}</b><br/>{d_str}", styles["table_cell"]),
                Paragraph(kw_str, styles["table_cell_bold"]),
                Paragraph(dim_str, styles["table_cell"]),
                Paragraph(str(s.total_points or len(pts)), styles["table_cell"]),
                Paragraph(str(ranked_cnt), styles["table_cell"]),
                Paragraph(f"#{s.average_rank:.1f}" if s.average_rank else "N/A", styles["table_cell_bold"]),
                Paragraph(f"{s.local_visibility_pct:.0f}%" if s.local_visibility_pct is not None else "0%", styles["table_cell_bold"])
            ])

        t_overview = Table(comp_overview_rows, colWidths=[100, 110, 90, 55, 60, 60, 65])
        t_overview.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.SLATE_50]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_overview)
        story.append(Spacer(1, 14))

        # Individual Scan Sections
        for idx, (s, pts) in enumerate(scans_sorted):
            d_str = s.started_at.strftime("%d %b %Y, %I:%M %p") if s.started_at else "N/A"
            kw_str = s.keyword_rel.keyword if getattr(s, 'keyword_rel', None) else (s.keyword or "Target Keyword")
            story.append(Paragraph(f"Scan #{s.id} — {d_str} ({s.grid_size}×{s.grid_size}, {s.radius_km} km)", styles["heading2"]))
            story.append(Paragraph(f"<b>Keyword:</b> {kw_str} | <b>Avg Rank:</b> #{s.average_rank or 'N/A'} | <b>Visibility:</b> {s.local_visibility_pct or 0}%", styles["body"]))
            story.append(Spacer(1, 6))

            dict_points = [
                {
                    "point_number": getattr(p, "point_number", 0),
                    "row": getattr(p, "row", 0),
                    "col": getattr(p, "col", 0),
                    "lat": getattr(p, "latitude", 0.0),
                    "lng": getattr(p, "longitude", 0.0),
                    "rank": getattr(p, "rank", None),
                    "status": getattr(p, "status", "NOT_FOUND")
                }
                for p in pts
            ]
            map_d = cls._create_map_drawing(s.grid_size, dict_points, s.center_name or "Business Center")
            story.append(map_d)
            story.append(Spacer(1, 14))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    @classmethod
    def generate_selected_point_pdf(
        cls,
        project: Any,
        scan: Any,
        point: Any,
        analysis_data: Dict[str, Any]
    ) -> bytes:
        """
        Generates a dedicated single-point deep dive report.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = cls._get_styles()
        story = []

        pt_num = getattr(point, "point_number", 0)
        rank_val = getattr(point, "rank", None)
        status_val = (getattr(point, "status", "") or "").upper()
        scanned_date_str = scan.started_at.strftime("%d %b %Y, %I:%M %p") if scan.started_at else "N/A"
        kw_str = scan.keyword_rel.keyword if getattr(scan, 'keyword_rel', None) else (scan.keyword or "Target Keyword")

        story.append(Paragraph(f"Point #{pt_num} Deep Dive Analysis — {project.name}", styles["title"]))
        story.append(Paragraph(
            f"<b>Keyword:</b> {kw_str} &nbsp;|&nbsp; <b>Scan ID:</b> #{scan.id} &nbsp;|&nbsp; <b>Scanned:</b> {scanned_date_str}",
            styles["subtitle"]
        ))
        story.append(HRFlowable(width="100%", thickness=1.5, color=cls.PRIMARY, spaceBefore=2, spaceAfter=10))

        # 1. Location & Ranking Summary
        rank_badge = f"RANK #{rank_val}" if rank_val else ("NOT FOUND" if status_val == "NOT_FOUND" else status_val)
        area_name_str = str(
            analysis_data.get("location", {}).get("area_name")
            or getattr(point, "area_name", None)
            or "Area name unavailable"
        )
        summary_pt_data = [
            [
                Paragraph("POINT NUMBER", styles["meta_label"]),
                Paragraph("AREA / LOCALITY", styles["meta_label"]),
                Paragraph("GPS COORDINATES", styles["meta_label"]),
                Paragraph("DISTANCE FROM CENTER", styles["meta_label"]),
                Paragraph("DIRECTION", styles["meta_label"]),
                Paragraph("OBSERVED RANK", styles["meta_label"])
            ],
            [
                Paragraph(f"Point #{pt_num}", styles["meta_val"]),
                Paragraph(area_name_str, styles["meta_val"]),
                Paragraph(f"{getattr(point, 'latitude', 0.0):.5f}, {getattr(point, 'longitude', 0.0):.5f}", styles["meta_val"]),
                Paragraph(f"{getattr(point, 'distance_km', 0.0) or 0.0} km", styles["meta_val"]),
                Paragraph(str(getattr(point, "direction", "Center") or "Center"), styles["meta_val"]),
                Paragraph(f"#{rank_val}" if rank_val else "Not Ranked", styles["meta_val"])
            ]
        ]
        t_pt_summary = Table(summary_pt_data, colWidths=[75, 120, 110, 95, 75, 65])
        t_pt_summary.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cls.SLATE_50),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t_pt_summary)
        story.append(Spacer(1, 12))

        # 2. WHAT / WHERE / HOW / WHY
        diag = analysis_data.get("diagnostics", {})
        story.append(Paragraph("Diagnostic Intelligence", styles["heading2"]))

        diag_content = [
            [
                Paragraph("<b>WHAT:</b>", styles["body_bold"]),
                Paragraph(diag.get("what", "Observed ranking result."), styles["body"])
            ],
            [
                Paragraph("<b>WHERE:</b>", styles["body_bold"]),
                Paragraph(diag.get("where", "Geographic coordinates and direction."), styles["body"])
            ],
            [
                Paragraph("<b>HOW:</b>", styles["body_bold"]),
                Paragraph(
                    "<br/>".join([f"• <b>{h['field']}:</b> {h['value']}" for h in diag.get("how", [])]) if diag.get("how") else "No direct profile attributes.",
                    styles["body"]
                )
            ],
            [
                Paragraph("<b>WHY:</b>", styles["body_bold"]),
                Paragraph(
                    "<br/>".join([f"• {w}" for w in diag.get("why", [])]) if diag.get("why") else "Insufficient evidence collected.",
                    styles["body"]
                )
            ]
        ]
        t_diag = Table(diag_content, colWidths=[65, 475])
        t_diag.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("BACKGROUND", (0, 0), (-1, -1), cls.SLATE_50),
        ]))
        story.append(t_diag)
        story.append(Spacer(1, 14))

        # 3. Competitors Above & Below
        comp_hier = analysis_data.get("competitors_hierarchy", {})
        above = comp_hier.get("competitors_above", [])
        below = comp_hier.get("competitors_below", [])
        target = comp_hier.get("target_business")

        story.append(Paragraph("Competitors Ranking at this Coordinate", styles["heading2"]))
        story.append(Paragraph(f"Scanned Result Depth: <b>Top {comp_hier.get('result_depth', 20)}</b>", styles["body"]))
        story.append(Spacer(1, 6))

        comp_headers = [
            Paragraph("Rank", styles["table_header"]),
            Paragraph("Business / Competitor", styles["table_header"]),
            Paragraph("Category", styles["table_header"]),
            Paragraph("Rating & Reviews", styles["table_header"]),
            Paragraph("Domain", styles["table_header"])
        ]
        comp_table_rows = [comp_headers]

        # Add competitors above
        for c in above:
            r_str = f"{c.get('rating')}★ ({c.get('reviews_count')})" if c.get("rating") else "—"
            comp_table_rows.append([
                Paragraph(f"#{c.get('position')}", styles["table_cell_bold"]),
                Paragraph(c.get("title", "")[:32], styles["table_cell"]),
                Paragraph(c.get("category", "—")[:20] if c.get("category") else "—", styles["table_cell"]),
                Paragraph(r_str, styles["table_cell"]),
                Paragraph(c.get("domain", "—")[:25] if c.get("domain") else "—", styles["table_cell"])
            ])

        # Add target business
        if target and rank_val:
            comp_table_rows.append([
                Paragraph(f"#{target.get('position')}", styles["table_cell_bold"]),
                Paragraph(f"<b>{target.get('title', project.name)} (YOUR BUSINESS)</b>", styles["table_cell_bold"]),
                Paragraph(target.get("category", "—")[:20] if target.get("category") else "—", styles["table_cell_bold"]),
                Paragraph(f"{target.get('rating', '')}★ ({target.get('reviews_count', '')})" if target.get("rating") else "—", styles["table_cell_bold"]),
                Paragraph(target.get("domain", project.domain or "—")[:25], styles["table_cell_bold"])
            ])

        # Add competitors below
        for c in below:
            r_str = f"{c.get('rating')}★ ({c.get('reviews_count')})" if c.get("rating") else "—"
            comp_table_rows.append([
                Paragraph(f"#{c.get('position')}", styles["table_cell"]),
                Paragraph(c.get("title", "")[:32], styles["table_cell"]),
                Paragraph(c.get("category", "—")[:20] if c.get("category") else "—", styles["table_cell"]),
                Paragraph(r_str, styles["table_cell"]),
                Paragraph(c.get("domain", "—")[:25] if c.get("domain") else "—", styles["table_cell"])
            ])

        t_c_detail = Table(comp_table_rows, colWidths=[45, 175, 105, 95, 120])
        t_c_detail.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cls.PRIMARY),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, cls.SLATE_200),
            ("BOX", (0, 0), (-1, -1), 1, cls.SLATE_200),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.SLATE_50]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_c_detail)
        story.append(Spacer(1, 14))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
