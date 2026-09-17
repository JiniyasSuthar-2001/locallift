import io
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class AuditPDFService:
    @staticmethod
    def generate_pdf(canonical_data: Dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Custom palette
        primary_color = colors.HexColor("#4F46E5") # Indigo
        slate_900 = colors.HexColor("#0F172A")
        slate_700 = colors.HexColor("#334155")
        slate_100 = colors.HexColor("#F1F5F9")
        emerald_700 = colors.HexColor("#047857")
        amber_700 = colors.HexColor("#B45309")
        rose_700 = colors.HexColor("#BE123C")

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=slate_900,
            spaceAfter=4
        )

        subtitle_style = ParagraphStyle(
            'DocSubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=slate_700,
            spaceAfter=12
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=primary_color,
            spaceBefore=14,
            spaceAfter=8
        )

        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=12,
            textColor=slate_700
        )

        table_header_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        )

        table_body_style = ParagraphStyle(
            'TableBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=slate_900
        )

        story = []

        # Header Info
        domain = canonical_data.get("domain", "Unknown Domain")
        crawl_id = canonical_data.get("crawl_id") or "N/A"
        timestamp = canonical_data.get("crawl_timestamp") or "N/A"
        analyzed_pages = canonical_data.get("analyzed_pages", 0)
        evaluated_rules = canonical_data.get("evaluated_rules", 0)
        total_checks = canonical_data.get("total_evaluated_checks", 0)
        score_available = canonical_data.get("score_available", False)
        health_score = canonical_data.get("health_score")

        story.append(Paragraph(f"Canonical Audit & Website Health Report", title_style))
        story.append(Paragraph(f"Domain: <b>{domain}</b> &nbsp;|&nbsp; Crawl ID: <b>{crawl_id}</b> &nbsp;|&nbsp; Timestamp: <b>{timestamp}</b>", subtitle_style))
        story.append(Spacer(1, 8))

        # Health Score Section
        story.append(Paragraph("1. Health Score & Metric Summary", section_heading))
        if score_available and health_score is not None:
            score_text = f"<b>{health_score}/100</b>"
        else:
            score_text = "<b>Not Yet Scored</b>"

        summary_box_data = [
            [
                Paragraph("Health Score", table_header_style),
                Paragraph("Analyzed Pages", table_header_style),
                Paragraph("Evaluated Rules", table_header_style),
                Paragraph("Total Evaluated Checks", table_header_style)
            ],
            [
                Paragraph(score_text, table_body_style),
                Paragraph(str(analyzed_pages), table_body_style),
                Paragraph(str(evaluated_rules), table_body_style),
                Paragraph(f"{analyzed_pages} pages × {evaluated_rules} rules = <b>{total_checks} checks</b>", table_body_style)
            ]
        ]

        t_summary = Table(summary_box_data, colWidths=[120, 100, 110, 210])
        t_summary.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, 1), slate_100),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_summary)
        story.append(Spacer(1, 12))

        # Audit Rule Breakdown & Execution Table
        story.append(Paragraph("2. Audit Rule Execution Table", section_heading))
        story.append(Paragraph(f"Dynamic Rule Calculation: <b>{analyzed_pages} analyzed pages × {evaluated_rules} evaluated rules = {total_checks} total checks</b>", body_style))
        story.append(Spacer(1, 6))

        rule_table_data = [
            [
                Paragraph("Rule ID", table_header_style),
                Paragraph("Category", table_header_style),
                Paragraph("Rule Name", table_header_style),
                Paragraph("Checked", table_header_style),
                Paragraph("Passed", table_header_style),
                Paragraph("Problems", table_header_style),
                Paragraph("Status", table_header_style),
                Paragraph("Validation Method", table_header_style)
            ]
        ]

        exec_results = canonical_data.get("rule_execution_results", [])
        for r in exec_results:
            rule_table_data.append([
                Paragraph(r.get("rule_id", ""), table_body_style),
                Paragraph(r.get("category", ""), table_body_style),
                Paragraph(r.get("rule_name", ""), table_body_style),
                Paragraph(str(r.get("pages_checked", 0)), table_body_style),
                Paragraph(str(r.get("passed", 0)), table_body_style),
                Paragraph(str(r.get("problems", 0)), table_body_style),
                Paragraph(f"<b>{r.get('status', '')}</b>", table_body_style),
                Paragraph(r.get("validation_method", ""), table_body_style)
            ])

        t_rules = Table(rule_table_data, colWidths=[55, 80, 110, 45, 45, 45, 60, 100])
        t_rules.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), slate_900),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_100]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(t_rules)
        story.append(Spacer(1, 14))

        # Schema & Structured Data Section
        story.append(Paragraph("3. Schema & Structured Data Evidence", section_heading))
        schema_sum = canonical_data.get("schema_summary", {})
        schema_box_data = [
            [
                Paragraph("Scanned", table_header_style),
                Paragraph("With Schema", table_header_style),
                Paragraph("Without Schema", table_header_style),
                Paragraph("Instances", table_header_style),
                Paragraph("Unique Types", table_header_style),
                Paragraph("Complete", table_header_style),
                Paragraph("Incomplete", table_header_style),
                Paragraph("Mismatches", table_header_style)
            ],
            [
                Paragraph(str(schema_sum.get("pages_scanned", 0)), table_body_style),
                Paragraph(str(schema_sum.get("pages_with_schema", 0)), table_body_style),
                Paragraph(str(schema_sum.get("pages_without_schema", 0)), table_body_style),
                Paragraph(str(schema_sum.get("total_schema_instances", 0)), table_body_style),
                Paragraph(str(schema_sum.get("unique_schema_types", 0)), table_body_style),
                Paragraph(str(schema_sum.get("complete_entities", 0)), table_body_style),
                Paragraph(str(schema_sum.get("incomplete_entities", 0)), table_body_style),
                Paragraph(str(schema_sum.get("potential_mismatches", 0)), table_body_style)
            ]
        ]
        t_schema = Table(schema_box_data, colWidths=[65, 70, 75, 60, 70, 65, 65, 70])
        t_schema.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), primary_color),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, 1), slate_100),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_schema)
        story.append(Spacer(1, 10))

        # Schema Types Detected List
        det_types = schema_sum.get("detected_types", [])
        if det_types:
            types_str = ", ".join([f"<b>{dt['type']}</b> ({dt['page_count']} pages)" for dt in det_types])
            story.append(Paragraph(f"Detected Types: {types_str}", body_style))
            story.append(Spacer(1, 10))

        # Robots.txt Section
        story.append(Paragraph("4. Robots.txt Technical Audit", section_heading))
        r_sum = canonical_data.get("robots_summary", {})
        robots_data = [
            [
                Paragraph("Robots URL", table_header_style),
                Paragraph("Fetch Status", table_header_style),
                Paragraph("HTTP Status", table_header_style),
                Paragraph("User Agent Groups", table_header_style),
                Paragraph("Allow Rules", table_header_style),
                Paragraph("Disallow Rules", table_header_style),
                Paragraph("Seed URL Result", table_header_style)
            ],
            [
                Paragraph(r_sum.get("robots_url", ""), table_body_style),
                Paragraph(r_sum.get("fetch_status", ""), table_body_style),
                Paragraph(str(r_sum.get("http_status", "")), table_body_style),
                Paragraph(str(r_sum.get("user_agent_groups", 0)), table_body_style),
                Paragraph(str(r_sum.get("allow_rules", 0)), table_body_style),
                Paragraph(str(r_sum.get("disallow_rules", 0)), table_body_style),
                Paragraph(r_sum.get("seed_url_result", ""), table_body_style)
            ]
        ]
        t_robots = Table(robots_data, colWidths=[140, 95, 55, 75, 55, 60, 60])
        t_robots.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), slate_900),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, 1), slate_100),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(t_robots)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
