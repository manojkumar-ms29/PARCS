"""Comprehensive Academic Project Report Builder for PARCS.

Generates PARCS_Project_Report.docx conforming to all formatting,
architectural, and technical accuracy requirements.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from PIL import Image

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml

import win32com.client

from report_utils import (
    add_page_border,
    add_chapter_heading,
    add_section_heading,
    add_subsection_heading,
    add_body_p,
    add_bullet_p,
    add_figure_image,
    add_academic_table,
    add_code_snippet,
)


def build_parcs_report(output_docx_path: str) -> None:
    doc = docx.Document()

    # -------------------------------------------------------------
    # Page setup - A4 with 0.8 in margins (academic standard)
    # -------------------------------------------------------------
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    # Apply page border to section 1
    add_page_border(section)

    # Ensure fixed SRM logo exists
    if not os.path.exists("scratch/srm_logo_fixed.png"):
        with Image.open("scratch/srm_logo.png") as img:
            img.save("scratch/srm_logo_fixed.png", "PNG", dpi=(300, 300))

    # =============================================================
    # PAGE 1: ORIGINAL COVER PAGE
    # =============================================================
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.line_spacing = 1.15
    run = p_title.add_run("Research AI: Generative AI-Based Research Paper Intelligence System")
    run.font.name = "Times New Roman"
    run.font.size = Pt(16)
    run.bold = True

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(4)
    run = p_sub.add_run("A Project report submitted to the")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dept.paragraph_format.space_before = Pt(0)
    p_dept.paragraph_format.space_after = Pt(4)
    run = p_dept.add_run("DEPARTMENT OF COMPUTER APPLICATIONS")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    p_pf = doc.add_paragraph()
    p_pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pf.paragraph_format.space_before = Pt(0)
    p_pf.paragraph_format.space_after = Pt(2)
    run = p_pf.add_run("in partial fulfilment of the requirements")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    p_award = doc.add_paragraph()
    p_award.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_award.paragraph_format.space_before = Pt(0)
    p_award.paragraph_format.space_after = Pt(4)
    run = p_award.add_run("for the award of the degree of")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    p_deg = doc.add_paragraph()
    p_deg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_deg.paragraph_format.space_before = Pt(0)
    p_deg.paragraph_format.space_after = Pt(14)
    run = p_deg.add_run("BACHELOR OF COMPUTER APPLICATIONS (HONOURS) IN DS")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True

    p_by = doc.add_paragraph()
    p_by.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_by.paragraph_format.space_before = Pt(0)
    p_by.paragraph_format.space_after = Pt(14)
    run = p_by.add_run("By")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    p_stud = doc.add_paragraph()
    p_stud.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_stud.paragraph_format.space_before = Pt(0)
    p_stud.paragraph_format.space_after = Pt(2)
    run = p_stud.add_run("SREE NITHI G")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True

    p_reg = doc.add_paragraph()
    p_reg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_reg.paragraph_format.space_before = Pt(0)
    p_reg.paragraph_format.space_after = Pt(24)
    run = p_reg.add_run("RA2331242010043")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True

    p_gui = doc.add_paragraph()
    p_gui.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_gui.paragraph_format.space_before = Pt(0)
    p_gui.paragraph_format.space_after = Pt(4)
    run = p_gui.add_run("Under the Guidance of")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    p_guide_name = doc.add_paragraph()
    p_guide_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_guide_name.paragraph_format.space_before = Pt(0)
    p_guide_name.paragraph_format.space_after = Pt(20)
    run = p_guide_name.add_run("Dr. BRINDHA.S, M.Sc., M.Phil., Ph.D.")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    p_logo = doc.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(14)
    run_logo = p_logo.add_run()
    run_logo.add_picture("scratch/srm_logo_fixed.png", width=Inches(3.3))

    p_univ = doc.add_paragraph()
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.paragraph_format.space_before = Pt(0)
    p_univ.paragraph_format.space_after = Pt(3)
    run = p_univ.add_run("SRM INSTITUTE OF SCIENCE AND TECHNOLOGY")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    p_fac = doc.add_paragraph()
    p_fac.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fac.paragraph_format.space_before = Pt(0)
    p_fac.paragraph_format.space_after = Pt(3)
    run = p_fac.add_run("Faculty of Science and Humanities")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)

    p_loc = doc.add_paragraph()
    p_loc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_loc.paragraph_format.space_before = Pt(0)
    p_loc.paragraph_format.space_after = Pt(50)
    run = p_loc.add_run("Kattankulathur– 603306")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(0)
    p_date.paragraph_format.space_after = Pt(0)
    run = p_date.add_run("October 2027")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    # =============================================================
    # PAGE 2: BONAFIDE CERTIFICATE
    # =============================================================
    doc.add_page_break()

    p_cert_title = doc.add_paragraph()
    p_cert_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert_title.paragraph_format.space_before = Pt(36)
    p_cert_title.paragraph_format.space_after = Pt(36)
    run = p_cert_title.add_run("BONAFIDE CERTIFICATE")
    run.font.name = "Times New Roman"
    run.font.size = Pt(15)
    run.bold = True

    p_cert_body = doc.add_paragraph()
    p_cert_body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_cert_body.paragraph_format.space_before = Pt(0)
    p_cert_body.paragraph_format.space_after = Pt(200)
    p_cert_body.paragraph_format.line_spacing = 1.5

    r1 = p_cert_body.add_run("This is to certify that the project report titled “")
    r1.font.name = "Times New Roman"; r1.font.size = Pt(11.5)
    r2 = p_cert_body.add_run("Research AI: Generative AI-Based Research Paper Intelligence System")
    r2.font.name = "Times New Roman"; r2.font.size = Pt(11.5); r2.bold = True
    r3 = p_cert_body.add_run("” is a Bonafide work carried out by ")
    r3.font.name = "Times New Roman"; r3.font.size = Pt(11.5)
    r4 = p_cert_body.add_run("SREE NITHI G (RA2331242010043)")
    r4.font.name = "Times New Roman"; r4.font.size = Pt(11.5); r4.bold = True
    r5 = p_cert_body.add_run(" Under my supervision for the award of the Degree of Bachelor of Computer Applications (Honours) in Data Science. To my knowledge the work reported herein is the original work done by this student.")
    r5.font.name = "Times New Roman"; r5.font.size = Pt(11.5)

    table_guide = doc.add_table(rows=3, cols=2)
    table_guide.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_guide.autofit = False
    for row in table_guide.rows:
        row.cells[0].width = Inches(3.3)
        row.cells[1].width = Inches(3.3)
    
    table_guide.cell(0, 0).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(0, 0).paragraphs[0].add_run("Dr. BRINDHA.S")
    r.font.name = "Times New Roman"; r.font.size = Pt(12); r.bold = True
    table_guide.cell(1, 0).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(1, 0).paragraphs[0].add_run("Assistant Professor,")
    r.font.name = "Times New Roman"; r.font.size = Pt(12)
    table_guide.cell(2, 0).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(2, 0).paragraphs[0].add_run("Department of Computer Applications")
    r.font.name = "Times New Roman"; r.font.size = Pt(12)

    table_guide.cell(0, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    table_guide.cell(0, 1).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(0, 1).paragraphs[0].add_run("Dr. P.J ARUL LEENA ROSE")
    r.font.name = "Times New Roman"; r.font.size = Pt(12); r.bold = True
    table_guide.cell(1, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    table_guide.cell(1, 1).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(1, 1).paragraphs[0].add_run("Professor& Head,")
    r.font.name = "Times New Roman"; r.font.size = Pt(12)
    table_guide.cell(2, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    table_guide.cell(2, 1).paragraphs[0].paragraph_format.space_after = Pt(2)
    r = table_guide.cell(2, 1).paragraphs[0].add_run("Department of Computer Applications")
    r.font.name = "Times New Roman"; r.font.size = Pt(12)

    p_space = doc.add_paragraph()
    p_space.paragraph_format.space_before = Pt(50)
    p_space.paragraph_format.space_after = Pt(0)

    table_exam = doc.add_table(rows=1, cols=2)
    table_exam.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_exam.autofit = False
    table_exam.rows[0].cells[0].width = Inches(3.3)
    table_exam.rows[0].cells[1].width = Inches(3.3)
    r = table_exam.cell(0, 0).paragraphs[0].add_run("INTERNAL EXAMINER")
    r.font.name = "Times New Roman"; r.font.size = Pt(12); r.bold = True
    table_exam.cell(0, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = table_exam.cell(0, 1).paragraphs[0].add_run("EXTERNAL EXAMINER")
    r.font.name = "Times New Roman"; r.font.size = Pt(12); r.bold = True

    # =============================================================
    # PAGE 3: ACKNOWLEDGEMENT
    # =============================================================
    doc.add_page_break()

    p_ack_title = doc.add_paragraph()
    p_ack_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack_title.paragraph_format.space_before = Pt(36)
    p_ack_title.paragraph_format.space_after = Pt(24)
    run = p_ack_title.add_run("ACKNOWLEDGEMENT")
    run.font.name = "Times New Roman"
    run.font.size = Pt(15)
    run.bold = True

    ack_paragraphs = [
        [("With profound gratitude to the Almighty, I take this chance to thank people who helped me to complete this project.", False)],
        [("I take this as a right opportunity to say THANKS to my parents who are there to stand with me always with the words “YOU CAN”.", False)],
        [("I wish to express my sincere gratitude to ", False), ("Dr. T.R. Paarivendhar", True), (", Chancellor, SRM Institute of Science and Technology who gave us the platform to establish me to reach greater heights.", False)],
        [("I am thankful to ", False), ("Dr. A. Duraisamy", True), (", Dean, Faculty of Science and Humanities, SRM Institute of Science & Technology for their unwavering support throughout my project.", False)],
        [("I earnestly thank ", False), ("Dr. S. Albert Antony Raj", True), (", Professor and Deputy Dean, College of Sciences, Faculty of science and Humanities, who always encourage me to do novel things.", False)],
        [("I earnestly thanks to ", False), ("Dr. P. J. Arul Leena Rose", True), (", Professor and Head, Department of Computer Applications, Faculty of Science and Humanities, for her valuable guidance and support to execute all incline in learning.", False)],
        [("It is my delight to thank my project guide ", False), ("Dr. Brindha S", True), (", Assistant Professor, Department of computer Applications, for her help, support, encouragement, suggestions, and guidance throughout the development phases of the project.", False)],
        [("I convey my gratitude to all the faculty members of the department who extended their support through valuable comments and suggestions during the reviews.", False)],
        [("A great note of gratitude to friends and people who are known and unknown to me who helped in carrying out this project work a successful one.", False)],
    ]

    for parts in ack_paragraphs:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.line_spacing = 1.15
        for text, bold in parts:
            r = p.add_run(text)
            r.font.name = "Times New Roman"
            r.font.size = Pt(11.5)
            r.bold = bold

    p_sig = doc.add_paragraph()
    p_sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sig.paragraph_format.space_before = Pt(28)
    p_sig.paragraph_format.space_after = Pt(0)
    r = p_sig.add_run("SREE NITHI G")
    r.font.name = "Times New Roman"
    r.font.size = Pt(12)
    r.bold = True

    # =============================================================
    # PAGE 4: TABLE OF CONTENTS
    # =============================================================
    doc.add_page_break()

    p_toc_title = doc.add_paragraph()
    p_toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_toc_title.paragraph_format.space_before = Pt(24)
    p_toc_title.paragraph_format.space_after = Pt(18)
    r = p_toc_title.add_run("TABLE OF CONTENTS")
    r.font.name = "Times New Roman"; r.font.size = Pt(16); r.bold = True

    # Word Table of Contents Field
    p_fld = doc.add_paragraph()
    p_fld.paragraph_format.space_after = Pt(6)
    r_fld = p_fld.add_run()
    fldChar1 = parse_xml(r'<w:fldChar xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fldCharType="begin"/>')
    instrText = parse_xml(r'<w:instrText xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText>')
    fldChar2 = parse_xml(r'<w:fldChar xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fldCharType="separate"/>')
    fldChar3 = parse_xml(r'<w:fldChar xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fldCharType="end"/>')
    r_fld._r.append(fldChar1)
    r_fld._r.append(instrText)
    r_fld._r.append(fldChar2)
    r_fld._r.append(fldChar3)

    # Initial formatted static TOC matching academic structure
    toc_entries = [
        ("1.  INTRODUCTION", "6", True),
        ("     1.1  Background of the Project", "6", False),
        ("     1.2  Problem Statement", "7", False),
        ("     1.3  Objectives of the Project", "8", False),
        ("     1.4  Scope of the Project", "8", False),
        ("     1.5  Organisation of the Report", "9", False),
        ("2.  LITERATURE STUDY", "10", True),
        ("     2.1  Introduction", "10", False),
        ("     2.2  Review of Relevant Research and Technical Concepts", "10", False),
        ("     2.3  Analysis of Existing Approaches", "13", False),
        ("     2.4  Research Gap", "14", False),
        ("     2.5  Summary", "15", False),
        ("3.  SOFTWARE REQUIREMENT ANALYSIS", "16", True),
        ("     3.1  Hardware Specification", "16", False),
        ("     3.2  Software Specification", "16", False),
        ("     3.3  About the Software and Its Features", "17", False),
        ("4.  SYSTEM ANALYSIS", "19", True),
        ("     4.1  Requirement Specification", "19", False),
        ("     4.2  Characteristics and Limitations of Existing Approaches", "21", False),
        ("     4.3  Proposed System", "22", False),
        ("     4.4  Software Requirement Specification", "23", False),
        ("5.  SYSTEM DESIGN", "25", True),
        ("     5.1  Introduction", "25", False),
        ("     5.2  System Architecture", "25", False),
        ("     5.3  Software Workflow Diagram", "27", False),
        ("     5.4  Use Case Diagram", "28", False),
        ("     5.5  Logical Component and Data Model Design", "30", False),
        ("     5.6  Activity Diagram", "31", False),
        ("     5.7  Data Flow Diagram", "33", False),
        ("     5.8  Design Considerations", "35", False),
        ("     5.9  Chapter Summary", "36", False),
        ("6.  SYSTEM IMPLEMENTATION", "37", True),
        ("     6.1  Introduction", "37", False),
        ("     6.2  Module Description", "38", False),
        ("     6.3  Validation Checks", "44", False),
        ("     6.4  Chapter Summary", "47", False),
        ("7.  TESTING", "48", True),
        ("     7.1  Test Cases", "48", False),
        ("     7.2  Unit Testing", "52", False),
        ("     7.3  Integrated Testing", "54", False),
        ("8.  RESULTS AND CONCLUSION", "58", True),
        ("     8.1  Results", "58", False),
        ("     8.2  Limitations", "60", False),
        ("     8.3  Future Enhancements", "61", False),
        ("     8.4  Conclusion", "63", False),
        ("9.  APPENDICES", "64", True),
        ("     9.1  Demonstration and Startup Instructions", "64", False),
        ("     9.2  Selected API Examples", "65", False),
        ("     9.3  Representative Source Code", "67", False),
        ("     9.4  User Documentation", "70", False),
        ("     9.5  Glossary", "71", False),
        ("10. BIBLIOGRAPHY", "73", True),
        ("     10.1 Books and Research Publications", "73", False),
        ("     10.2 Official Technical Documentation", "74", False),
    ]

    # Create two-column table for aligned dots and page numbers
    t_toc = doc.add_table(rows=len(toc_entries), cols=2)
    t_toc.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_toc.autofit = False
    for r_idx, (entry_title, page_num, is_bold) in enumerate(toc_entries):
        row = t_toc.rows[r_idx]
        row.cells[0].width = Inches(5.9)
        row.cells[1].width = Inches(0.8)
        
        # Left title
        p_l = row.cells[0].paragraphs[0]
        p_l.paragraph_format.space_before = Pt(1 if not is_bold else 4)
        p_l.paragraph_format.space_after = Pt(1 if not is_bold else 2)
        r_l = p_l.add_run(entry_title)
        r_l.font.name = "Times New Roman"
        r_l.font.size = Pt(10.5 if is_bold else 10)
        r_l.bold = is_bold
        
        # Right page
        p_r = row.cells[1].paragraphs[0]
        p_r.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p_r.paragraph_format.space_before = Pt(1 if not is_bold else 4)
        p_r.paragraph_format.space_after = Pt(1 if not is_bold else 2)
        r_r = p_r.add_run(page_num)
        r_r.font.name = "Times New Roman"
        r_r.font.size = Pt(10.5 if is_bold else 10)
        r_r.bold = is_bold

    # =============================================================
    # PAGE 5: ABSTRACT
    # =============================================================
    doc.add_page_break()

    p_abs_title = doc.add_paragraph()
    p_abs_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_title.paragraph_format.space_before = Pt(24)
    p_abs_title.paragraph_format.space_after = Pt(12)
    r = p_abs_title.add_run("ABSTRACT")
    r.font.name = "Times New Roman"; r.font.size = Pt(15); r.bold = True

    p_abs_sub = doc.add_paragraph()
    p_abs_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_sub.paragraph_format.space_before = Pt(0)
    p_abs_sub.paragraph_format.space_after = Pt(18)
    r = p_abs_sub.add_run("PARCS: Performance Anomaly & Regression Correlation System")
    r.font.name = "Times New Roman"; r.font.size = Pt(13); r.bold = True

    add_body_p(
        doc,
        "Modern laptop computers equipped with Microsoft Windows Modern Standby (S0 Low Power Idle, or S0ix) "
        "are architected to maintain continuous network connectivity and rapid instant-on wake performance "
        "while conserving battery power during system sleep states. To achieve competitive battery longevity, "
        "the operating system and platform hardware must achieve deep hardware low-power states, formally designated "
        "as Deepest Runtime Idle Power State (DRIPS), targeting an idle residency exceeding 95% of sleep duration. "
        "However, in practice, Modern Standby performance frequently degrades due to misbehaving device drivers, "
        "faulty power management policies, operating system hotfixes, or uncoordinated background services that prevent "
        "the SoC from entering or sustaining DRIPS states. The native diagnostic utility provided by Windows, "
        "powercfg /sleepstudy, operates strictly in a stateless, session-by-session manner. It emits isolated HTML "
        "or XML diagnostic reports after individual sessions or short collection windows, lacking longitudinal persistence, "
        "machine-specific statistical baselines, multi-session trend analysis, and automated correlation with system changes."
    )

    add_body_p(
        doc,
        "This project presents PARCS (Performance Anomaly & Regression Correlation System), a data-engineering-first "
        "telemetry analytics application designed to continuously ingest, persist, analyze, and diagnose Modern Standby "
        "behavior. PARCS establishes a robust, decoupled, and zero-server architecture: Windows telemetry is extracted "
        "via modular collectors (SleepStudy, installed driver snapshots, Windows Update installation histories, and "
        "Windows Event Log power-state records), preserved in raw JSON format, cleaned and schema-validated via an ETL "
        "pipeline, and persisted into an immutable Apache Parquet columnar data lake. Fast, SQL-based analytical queries "
        "are executed directly against the columnar store using embedded DuckDB without requiring database servers."
    )

    add_body_p(
        doc,
        "To reliably detect genuine performance degradations without conflating them with normal operational variances, "
        "PARCS implements machine-specific statistical baselines utilizing robust non-parametric estimators, specifically "
        "the Median, Median Absolute Deviation (MAD), and Interquartile Range (IQR). Individual sessions are scored "
        "for point anomalies using Modified Z-scores. To eliminate false alarms triggered by transient battery spikes, "
        "PARCS introduces a directional sustained regression detector that requires consecutive qualifying degraded sessions "
        "in strict timestamp order. When a sustained regression is established, an explainable temporal change correlation "
        "engine searches within configurable pre- and post-regression time windows to identify temporally associated system "
        "events, such as device driver updates, Windows patches, or kernel power errors. Crucially, PARCS maintains strict "
        "epistemological boundaries, presenting temporal relationships as evidence for engineering investigation rather "
        "than asserting mathematical proof of causation."
    )

    add_body_p(
        doc,
        "The analytical capabilities are exposed through a high-performance FastAPI REST backend and visualized in an "
        "interactive Streamlit dashboard. In this Minimum Viable Product (MVP) release, the system was exhaustively verified "
        "against an automated test suite of 253 test cases (0 failures, 1 maintenance warning), achieving 100% pass rates across "
        "isolation, evaluation-scope partitioning (subsequent vs all), zero-MAD fallback handling, insufficient-history "
        "readiness guards, and machine-specific synthetic-data provenance. Deterministic synthetic fixtures (22 session records "
        "and 4 change records across DEMO-MACHINE-READY and DEMO-MACHINE-SPARSE) demonstrate end-to-end functionality. "
        "The report clearly distinguishes synthetic demonstration data from genuine laptop telemetry and details future "
        "directions for background daemon execution and enterprise fleet diagnostics."
    )

    # =============================================================
    # CHAPTER 1: INTRODUCTION
    # =============================================================
    doc.add_page_break()
    add_chapter_heading(doc, "1. INTRODUCTION")

    add_section_heading(doc, "1.1 Background of the Project")
    add_body_p(
        doc,
        "Personal computing architectures have undergone a profound paradigm shift over the past decade. "
        "Historically, laptop power management relied on the Advanced Configuration and Power Interface (ACPI) "
        "S3 state, commonly known as Suspend-to-RAM. In an S3 sleep transition, the central processing unit (CPU), "
        "system clocks, and peripheral buses are powered down entirely, leaving only system memory actively refreshed. "
        "While S3 sleep yielded predictable, near-zero battery consumption, it suffered from notable operational "
        "disadvantages: waking the machine required several seconds of hardware re-initialization, and the system "
        "remained completely inert, incapable of receiving background updates, push notifications, or network maintenance."
    )
    add_body_p(
        doc,
        "To deliver a modern smartphone-like user experience—characterized by instant-on resumption (under 500 milliseconds) "
        "and continuous background synchronization—Microsoft and silicon vendors (Intel, AMD, Qualcomm) introduced "
        "Modern Standby, formally designated as S0 Low Power Idle (S0ix). Unlike legacy S3 sleep, a machine entering "
        "Modern Standby remains in the ACPI S0 working state. The operating system places the processor cores into "
        "deep C-states (such as PC10), switches off display pipelines, suspends non-critical user-mode processes, and "
        "signals the platform hardware to enter the Deepest Runtime Idle Power State (DRIPS). When functioning correctly, "
        "the platform achieves DRIPS residency exceeding 95% of the sleep duration, achieving milliwatt-level quiescent "
        "power consumption."
    )
    add_body_p(
        doc,
        "However, Modern Standby places tremendous reliance on the holistic cooperation of the hardware and software "
        "ecosystem. Because the platform remains awake in S0, any misconfigured peripheral device driver, uncoordinated "
        "network wake packet, background audio stream, or corrupt system service can prevent the hardware power controller "
        "from entering DRIPS. When this occurs, laptops experience severe battery drain while sleeping in backpacks, "
        "excessive thermal dissipation, fan spinning during transport, and unexpected battery depletion upon opening the lid. "
        "Diagnosing these failures represents one of the most persistent and frustrating challenges in modern PC systems engineering."
    )

    add_section_heading(doc, "1.2 Problem Statement")
    add_body_p(
        doc,
        "Despite the pervasive nature of Modern Standby battery drain issues, existing operating system diagnostics "
        "suffer from severe architectural and operational limitations:"
    )
    add_bullet_p(
        doc,
        "The primary built-in diagnostic tool, powercfg /sleepstudy, produces isolated, single-session HTML or XML "
        "reports. It lacks longitudinal memory, meaning it cannot track how a machine's sleep efficiency evolves across "
        "days, weeks, or months.",
        bold_prefix="Stateless Diagnostic Tooling: "
    )
    add_bullet_p(
        doc,
        "Standard battery drain rates vary significantly between different laptop models depending on battery capacity, "
        "installed memory, and attached peripherals. Static thresholding (e.g. flagging any session draining more than 1% per hour) "
        "produces unacceptable rates of false alarms on high-performance machines and missed detections on ultra-low-power systems.",
        bold_prefix="Absence of Machine-Specific Baselines: "
    )
    add_bullet_p(
        doc,
        "Transient factors—such as an active user-initiated download, temporary background virus scan, or brief audio playback—"
        "can cause an isolated session to experience poor DRIPS residency. Existing tools treat every isolated spike as an anomaly, "
        "failing to distinguish temporary operational blips from genuine, persistent regressions.",
        bold_prefix="Conflation of Transient Spikes with Sustained Regressions: "
    )
    add_bullet_p(
        doc,
        "When sleep degradation occurs, diagnosing the underlying cause requires manually cross-referencing SleepStudy data "
        "with device manager snapshots, Windows Update history, and Windows Event Viewer logs. These telemetry sources are "
        "siloed in disparate formats, making root-cause triage time-consuming, tedious, and error-prone.",
        bold_prefix="Disconnected System Event Telemetry: "
    )
    add_bullet_p(
        doc,
        "Many commercial endpoint management tools upload extensive proprietary telemetry to cloud backends, introducing "
        "data privacy concerns, latency, subscription costs, and heavyweight database infrastructure dependencies.",
        bold_prefix="Lack of Lightweight, Privacy-Preserving Local Analytics: "
    )

    add_section_heading(doc, "1.3 Objectives of the Project")
    add_body_p(
        doc,
        "The overarching objective of the PARCS project is to develop an automated, explainable, and zero-server "
        "data engineering telemetry system that tracks Windows Modern Standby performance over time, detects statistically "
        "grounded regressions, and correlates performance changes with recorded system events. The specific technical "
        "objectives are as follows:"
    )
    add_bullet_p(
        doc,
        "To engineer modular, Windows-native telemetry collectors for SleepStudy reports, installed driver snapshots, "
        "Windows Update installation history, and Windows Event Log power transitions.",
        bold_prefix="Objective 1 (Telemetry Collection): "
    )
    add_bullet_p(
        doc,
        "To implement an immutable raw-data preservation layer and an ETL pipeline that validates and normalizes diverse "
        "telemetry sources into standardized tabular data structures.",
        bold_prefix="Objective 2 (Data Engineering & Normalization): "
    )
    add_bullet_p(
        doc,
        "To persist normalized telemetry in Apache Parquet columnar files and enable sub-second SQL analytical querying "
        "via embedded DuckDB without running an external database daemon.",
        bold_prefix="Objective 3 (Columnar Persistence & Analytical Store): "
    )
    add_bullet_p(
        doc,
        "To compute machine-specific, robust statistical baselines (Median, MAD, IQR) strictly partitioned by machine identity, "
        "enforcing observation readiness requirements (minimum 10 observations) and zero-MAD fallbacks.",
        bold_prefix="Objective 4 (Machine-Specific Baselines): "
    )
    add_bullet_p(
        doc,
        "To detect explainable point anomalies using robust Modified Z-scores and identify sustained performance regressions "
        "via directional consecutive degradation streaks (minimum 3 sessions) in chronological order.",
        bold_prefix="Objective 5 (Anomaly & Sustained Regression Detection): "
    )
    add_bullet_p(
        doc,
        "To correlate identified regressions with recorded system events occurring within configurable temporal windows "
        "([-24 hours, +2 hours]), explicitly preserving non-causal epistemological boundaries.",
        bold_prefix="Objective 6 (Temporal Change Correlation): "
    )
    add_bullet_p(
        doc,
        "To expose analytics via a modular FastAPI REST service and deliver an interactive visual dashboard in Streamlit.",
        bold_prefix="Objective 7 (Service & Interactive Visualization): "
    )
    add_bullet_p(
        doc,
        "To validate the system through exhaustive unit and integration testing (253 automated tests), verifying prospective "
        "baseline isolation, evaluation-scope controls, and synthetic data provenance.",
        bold_prefix="Objective 8 (Rigorous Verification & Quality Assurance): "
    )

    add_section_heading(doc, "1.4 Scope of the Project")
    add_body_p(
        doc,
        "The scope of PARCS is focused specifically on client-side Windows Modern Standby performance telemetry and "
        "longitudinal diagnostics. The functional boundaries of the current implementation encompass:"
    )
    add_bullet_p(
        doc,
        "Automated extraction from powercfg /sleepstudy, Windows Plug-and-Play (PnP) driver enumeration, Windows Update "
        "hotfix metadata, and Microsoft-Windows-Kernel-Power event logs.",
        bold_prefix="Supported Telemetry: "
    )
    add_bullet_p(
        doc,
        "Standardized Parquet datasets (data/processed/sleepstudy.parquet and data/processed/changes.parquet) querying "
        "in-process through DuckDB.",
        bold_prefix="Analytical Data Architecture: "
    )
    add_bullet_p(
        doc,
        "Evaluation of DRIPS percentage, battery drain rate (mW), and total battery drain percentage against machine-specific baselines.",
        bold_prefix="Core Performance Metrics: "
    )
    add_bullet_p(
        doc,
        "Evaluation-scope controls (subsequent prospective evaluation vs all-scope complete dataset scoring) with strict "
        "contamination guards.",
        bold_prefix="Prospective Partitioning: "
    )
    add_bullet_p(
        doc,
        "Deterministic synthetic fixtures (DEMO-MACHINE-READY with 14 baseline + 4 degraded sessions, and DEMO-MACHINE-SPARSE "
        "with 4 sessions), explicitly tagged with is_synthetic: True.",
        bold_prefix="Demonstration Scope: "
    )
    add_body_p(
        doc,
        "Explicit Non-Goals and Out-of-Scope Items: PARCS does NOT modify kernel-mode ACPI drivers, alter firmware power registers, "
        "execute automated driver rollback or uninstall actions, or ingest proprietary cloud telemetry. Genuine physical laptop "
        "telemetry collection is implemented in collectors but was not deployed long-term; all reported end-to-end multi-session "
        "audit results are based strictly on synthetic demonstration fixtures."
    )

    add_section_heading(doc, "1.5 Organisation of the Report")
    add_body_p(
        doc,
        "This project report is organized into ten comprehensive chapters designed to document the development, architecture, "
        "and empirical verification of PARCS in a structured, academic manner:"
    )
    add_bullet_p(
        doc,
        "Introduces the operational background of Windows Modern Standby, articulates the problem statement, defines project objectives, and outlines the functional scope.",
        bold_prefix="Chapter 1 (Introduction): "
    )
    add_bullet_p(
        doc,
        "Surveys foundational literature in ACPI power management, robust statistical process monitoring, time-series anomaly detection, temporal event correlation, and columnar analytics, identifying the technical research gap.",
        bold_prefix="Chapter 2 (Literature Study): "
    )
    add_bullet_p(
        doc,
        "Details hardware configurations, software technology stacks (Python, Parquet, DuckDB, FastAPI, Streamlit, pytest), and technical feature rationale.",
        bold_prefix="Chapter 3 (Software Requirement Analysis): "
    )
    add_bullet_p(
        doc,
        "Presents the formal Software Requirement Specification (SRS), enumerating functional and non-functional requirements and analyzing architectural constraints.",
        bold_prefix="Chapter 4 (System Analysis): "
    )
    add_bullet_p(
        doc,
        "Details the multi-tiered system design, including the system architecture, software workflow, use case model, logical component structure, activity flow, and Level-0/Level-1 data flow diagrams.",
        bold_prefix="Chapter 5 (System Design): "
    )
    add_bullet_p(
        doc,
        "Documents the concrete implementation of collectors, ETL pipelines, Parquet/DuckDB storage, baseline estimators, streak-based regression detection, correlation algorithms, API routes, and dashboard interfaces.",
        bold_prefix="Chapter 6 (System Implementation): "
    )
    add_bullet_p(
        doc,
        "Presents the testing methodology, formal test case specifications, unit testing regimes, and integrated acceptance audit results (253 passing automated tests, 0 failures, 1 warning).",
        bold_prefix="Chapter 7 (Testing): "
    )
    add_bullet_p(
        doc,
        "Synthesizes experimental results, articulates system limitations, defines future research directions, and presents concluding observations.",
        bold_prefix="Chapter 8 (Results and Conclusion): "
    )
    add_bullet_p(
        doc,
        "Supplies supplementary technical materials, including startup instructions, API payloads, representative source code excerpts, user documentation, and an academic glossary.",
        bold_prefix="Chapter 9 (Appendices): "
    )
    add_bullet_p(
        doc,
        "Lists authentic academic books, research papers, and official technical documentation consulted during project execution.",
        bold_prefix="Chapter 10 (Bibliography): "
    )

    doc.save(output_docx_path)
    print(f"Completed Chapter 1 and preliminary pages saved to {output_docx_path}.")

if __name__ == "__main__":
    build_parcs_report("scratch/report_ch1.docx")
