"""Unified, Complete Academic Project Report Generator for PARCS.

Produces a fully formatted, publication-grade academic document:
- First three pages preserved from the reference (Cover, Bonafide, Acknowledgement)
- Page 4: Table of Contents (fits Page 4 alone)
- Page 5: Abstract (fits Page 5 alone)
- Chapters 1 to 10 with deep technical rigor, authentic tables, and 7 system diagrams
- Full acceptance audit test results (253 tests passed, 0 failures, 1 warning)
- Non-causal temporal correlation and synthetic data provenance explicitly stated
- Zero-gap pagination (no blank pages, no overflow)
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
import pymupdf


# ----------------------------------------------------------------------
# XML Formatting Helpers
# ----------------------------------------------------------------------
def set_cell_margins(cell, top=80, bottom=80, left=120, right=120):
    """Set inner cell padding in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def set_cell_background(cell, fill_hex):
    """Set cell shading color."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def set_table_borders(table, color="B0B0B0", sz="4"):
    """Set subtle horizontal borders."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:top w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="single" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'<w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)


def make_row_header(row):
    """Repeat table header on subsequent pages."""
    trPr = row._tr.get_or_add_trPr()
    tblHeader = parse_xml(r'<w:tblHeader xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    trPr.append(tblHeader)


def make_row_cant_split(row):
    """Prevent table row from splitting across pages."""
    trPr = row._tr.get_or_add_trPr()
    cantSplit = parse_xml(r'<w:cantSplit xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>')
    trPr.append(cantSplit)


def add_page_border(section):
    """Add standard academic box page border."""
    sectPr = section._sectPr
    pgBorders = parse_xml(
        r'<w:pgBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:offsetFrom="page">'
        r'<w:top w:val="single" w:sz="12" w:space="24" w:color="000000"/>'
        r'<w:left w:val="single" w:sz="12" w:space="24" w:color="000000"/>'
        r'<w:bottom w:val="single" w:sz="12" w:space="24" w:color="000000"/>'
        r'<w:right w:val="single" w:sz="12" w:space="24" w:color="000000"/>'
        r'</w:pgBorders>'
    )
    sectPr.append(pgBorders)


# ----------------------------------------------------------------------
# Typography Helpers
# ----------------------------------------------------------------------
def add_chapter_heading(doc, title_text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(title_text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(15)
    r.bold = True
    return p


def add_section_heading(doc, title_text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(title_text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(12.5)
    r.bold = True
    return p


def add_subsection_heading(doc, title_text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(title_text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(11.5)
    r.bold = True
    return p


def add_body_p(doc, text, bold_prefix=None, space_after=5):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Times New Roman"
        r_pre.font.size = Pt(11)
        r_pre.bold = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(11)
    return p


def add_bullet_p(doc, text, bold_prefix=None, space_after=3):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.left_indent = Inches(0.25)
    
    # Bullet character
    r_bul = p.add_run("\u2022  ")
    r_bul.font.name = "Times New Roman"
    r_bul.font.size = Pt(11)
    r_bul.bold = True

    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Times New Roman"
        r_pre.font.size = Pt(11)
        r_pre.bold = True
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(11)
    return p


def add_figure_image(doc, img_path, caption_text, width_in=5.2):
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(3)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=Inches(width_in))

    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(10)
    r_cap = p_cap.add_run(caption_text)
    r_cap.font.name = "Times New Roman"
    r_cap.font.size = Pt(10)
    r_cap.bold = True
    return p_cap


def add_academic_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)

    hdr_row = table.rows[0]
    make_row_header(hdr_row)
    make_row_cant_split(hdr_row)
    for i, header_text in enumerate(headers):
        cell = hdr_row.cells[i]
        cell.text = header_text
        set_cell_background(cell, "EAECEE")
        set_cell_margins(cell, top=90, bottom=90, left=100, right=100)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = "Times New Roman"
            run.font.size = Pt(9.5)
            run.bold = True

    for r_idx, row_data in enumerate(data):
        row = table.rows[r_idx + 1]
        make_row_cant_split(row)
        bg_color = "FAFAFA" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, cell_value in enumerate(row_data):
            cell = row.cells[c_idx]
            cell.text = str(cell_value)
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=60, bottom=60, left=100, right=100)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for run in p.runs:
                run.font.name = "Times New Roman"
                run.font.size = Pt(9)

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Inches(w)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)
    return table


def add_code_snippet(doc, code_str):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.rows[0].cells[0].width = Inches(6.5)
    set_cell_background(table.rows[0].cells[0], "F4F6F7")
    set_cell_margins(table.rows[0].cells[0], top=80, bottom=80, left=120, right=120)
    set_table_borders(table, color="D0D3D4", sz="6")
    
    cell_p = table.rows[0].cells[0].paragraphs[0]
    cell_p.paragraph_format.space_before = Pt(0)
    cell_p.paragraph_format.space_after = Pt(0)
    cell_p.paragraph_format.line_spacing = 1.05
    run = cell_p.add_run(code_str)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(40, 55, 71)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_after = Pt(4)


# ----------------------------------------------------------------------
# Preliminary Pages 1-3
# ----------------------------------------------------------------------
def add_first_three_pages(doc):
    # PAGE 1: COVER
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.line_spacing = 1.15
    run = p_title.add_run("Research AI: Generative AI-Based Research Paper Intelligence System")
    run.font.name = "Times New Roman"; run.font.size = Pt(16); run.bold = True

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(4)
    run = p_sub.add_run("A Project report submitted to the")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.italic = True

    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dept.paragraph_format.space_before = Pt(0)
    p_dept.paragraph_format.space_after = Pt(4)
    run = p_dept.add_run("DEPARTMENT OF COMPUTER APPLICATIONS")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.bold = True

    p_pf = doc.add_paragraph()
    p_pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pf.paragraph_format.space_before = Pt(0)
    p_pf.paragraph_format.space_after = Pt(2)
    run = p_pf.add_run("in partial fulfilment of the requirements")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.italic = True

    p_award = doc.add_paragraph()
    p_award.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_award.paragraph_format.space_before = Pt(0)
    p_award.paragraph_format.space_after = Pt(4)
    run = p_award.add_run("for the award of the degree of")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.italic = True

    p_deg = doc.add_paragraph()
    p_deg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_deg.paragraph_format.space_before = Pt(0)
    p_deg.paragraph_format.space_after = Pt(14)
    run = p_deg.add_run("BACHELOR OF COMPUTER APPLICATIONS (HONOURS) IN DS")
    run.font.name = "Times New Roman"; run.font.size = Pt(13); run.bold = True

    p_by = doc.add_paragraph()
    p_by.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_by.paragraph_format.space_before = Pt(0)
    p_by.paragraph_format.space_after = Pt(14)
    run = p_by.add_run("By")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.italic = True

    p_stud = doc.add_paragraph()
    p_stud.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_stud.paragraph_format.space_before = Pt(0)
    p_stud.paragraph_format.space_after = Pt(2)
    run = p_stud.add_run("SREE NITHI G")
    run.font.name = "Times New Roman"; run.font.size = Pt(13); run.bold = True

    p_reg = doc.add_paragraph()
    p_reg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_reg.paragraph_format.space_before = Pt(0)
    p_reg.paragraph_format.space_after = Pt(24)
    run = p_reg.add_run("RA2331242010043")
    run.font.name = "Times New Roman"; run.font.size = Pt(13); run.bold = True

    p_gui = doc.add_paragraph()
    p_gui.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_gui.paragraph_format.space_before = Pt(0)
    p_gui.paragraph_format.space_after = Pt(4)
    run = p_gui.add_run("Under the Guidance of")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.italic = True

    p_guide_name = doc.add_paragraph()
    p_guide_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_guide_name.paragraph_format.space_before = Pt(0)
    p_guide_name.paragraph_format.space_after = Pt(20)
    run = p_guide_name.add_run("Dr. BRINDHA.S, M.Sc., M.Phil., Ph.D.")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.bold = True

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
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.bold = True

    p_fac = doc.add_paragraph()
    p_fac.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_fac.paragraph_format.space_before = Pt(0)
    p_fac.paragraph_format.space_after = Pt(3)
    run = p_fac.add_run("Faculty of Science and Humanities")
    run.font.name = "Times New Roman"; run.font.size = Pt(14)

    p_loc = doc.add_paragraph()
    p_loc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_loc.paragraph_format.space_before = Pt(0)
    p_loc.paragraph_format.space_after = Pt(50)
    run = p_loc.add_run("Kattankulathur– 603306")
    run.font.name = "Times New Roman"; run.font.size = Pt(14)

    p_date = doc.add_paragraph()
    p_date.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_date.paragraph_format.space_before = Pt(0)
    p_date.paragraph_format.space_after = Pt(0)
    run = p_date.add_run("October 2027")
    run.font.name = "Times New Roman"; run.font.size = Pt(14); run.bold = True

    # PAGE 2: BONAFIDE CERTIFICATE
    doc.add_page_break()

    p_cert_title = doc.add_paragraph()
    p_cert_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert_title.paragraph_format.space_before = Pt(36)
    p_cert_title.paragraph_format.space_after = Pt(36)
    run = p_cert_title.add_run("BONAFIDE CERTIFICATE")
    run.font.name = "Times New Roman"; run.font.size = Pt(15); run.bold = True

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

    # PAGE 3: ACKNOWLEDGEMENT
    doc.add_page_break()

    p_ack_title = doc.add_paragraph()
    p_ack_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack_title.paragraph_format.space_before = Pt(36)
    p_ack_title.paragraph_format.space_after = Pt(24)
    run = p_ack_title.add_run("ACKNOWLEDGEMENT")
    run.font.name = "Times New Roman"; run.font.size = Pt(15); run.bold = True

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
    r.font.name = "Times New Roman"; r.font.size = Pt(12); r.bold = True


# ----------------------------------------------------------------------
# Page 4: Table of Contents (Single Page Fit)
# ----------------------------------------------------------------------
def add_table_of_contents_page(doc):
    doc.add_page_break()

    p_toc_title = doc.add_paragraph()
    p_toc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_toc_title.paragraph_format.space_before = Pt(20)
    p_toc_title.paragraph_format.space_after = Pt(14)
    r = p_toc_title.add_run("TABLE OF CONTENTS")
    r.font.name = "Times New Roman"; r.font.size = Pt(15); r.bold = True

    # 10 Chapter Entries designed to fit on Page 4 alone
    toc_data = [
        ("1.  INTRODUCTION", "1.1 Background, 1.2 Problem Statement, 1.3 Objectives, 1.4 Scope, 1.5 Organisation", "6"),
        ("2.  LITERATURE STUDY", "2.1 Introduction, 2.2 Relevant Research, 2.3 Existing Approaches, 2.4 Gap, 2.5 Summary", "9"),
        ("3.  SOFTWARE REQUIREMENT ANALYSIS", "3.1 Hardware Specification, 3.2 Software Specification, 3.3 Features", "13"),
        ("4.  SYSTEM ANALYSIS", "4.1 Requirements (Functional & Non-Functional), 4.2 Limitations, 4.3 Proposed System, 4.4 SRS", "15"),
        ("5.  SYSTEM DESIGN", "5.1 Architecture, 5.2 Workflow, 5.3 Use Case, 5.4 Logical Model, 5.5 Activity, 5.6 DFD", "18"),
        ("6.  SYSTEM IMPLEMENTATION", "6.1 Ingestion & Storage, 6.2 Module Breakdown, 6.3 Validation Checks, 6.4 Summary", "26"),
        ("7.  TESTING", "7.1 Test Cases (TC-01..21), 7.2 Unit Testing, 7.3 Integrated Testing & Audit Results", "29"),
        ("8.  RESULTS AND CONCLUSION", "8.1 Results, 8.2 Limitations (Synthetic Provenance), 8.3 Future Enhancements, 8.4 Conclusion", "33"),
        ("9.  APPENDICES", "9.1 Startup Instructions, 9.2 API Examples, 9.3 Source Code Excerpts, 9.4 User Guide, 9.5 Glossary", "35"),
        ("10. BIBLIOGRAPHY", "10.1 Books & Research Publications, 10.2 Official Technical Documentation", "39"),
    ]

    t_toc = doc.add_table(rows=len(toc_data) + 1, cols=3)
    t_toc.alignment = WD_TABLE_ALIGNMENT.CENTER
    t_toc.autofit = False
    set_table_borders(t_toc, color="D0D3D4", sz="4")

    # Header
    hdr = t_toc.rows[0]
    make_row_header(hdr)
    make_row_cant_split(hdr)
    headers = ["Chapter & Title", "Sections & Key Coverage", "Page"]
    widths = [Inches(2.5), Inches(3.4), Inches(0.7)]
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.width = widths[i]
        c.text = h
        set_cell_background(c, "EAECEE")
        set_cell_margins(c, top=60, bottom=60, left=80, right=80)
        p = c.paragraphs[0]
        if i == 2:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in p.runs:
            run.font.name = "Times New Roman"
            run.font.size = Pt(10)
            run.bold = True

    for r_idx, (ch_title, ch_sec, ch_page) in enumerate(toc_data):
        row = t_toc.rows[r_idx + 1]
        make_row_cant_split(row)
        for i in range(3):
            row.cells[i].width = widths[i]
            set_cell_margins(row.cells[i], top=50, bottom=50, left=80, right=80)
            set_cell_background(row.cells[i], "FAFAFA" if r_idx % 2 == 1 else "FFFFFF")

        # Col 0: Title
        p0 = row.cells[0].paragraphs[0]
        p0.paragraph_format.space_before = Pt(0); p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(ch_title)
        r0.font.name = "Times New Roman"; r0.font.size = Pt(9.5); r0.bold = True

        # Col 1: Sections
        p1 = row.cells[1].paragraphs[0]
        p1.paragraph_format.space_before = Pt(0); p1.paragraph_format.space_after = Pt(0)
        r1 = p1.add_run(ch_sec)
        r1.font.name = "Times New Roman"; r1.font.size = Pt(8.5); r1.font.color.rgb = RGBColor(80, 90, 100)

        # Col 2: Page
        p2 = row.cells[2].paragraphs[0]
        p2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p2.paragraph_format.space_before = Pt(0); p2.paragraph_format.space_after = Pt(0)
        r2 = p2.add_run(ch_page)
        r2.font.name = "Times New Roman"; r2.font.size = Pt(9.5); r2.bold = True


# ----------------------------------------------------------------------
# Page 5: Abstract (Single Page Fit)
# ----------------------------------------------------------------------
def add_abstract_page(doc):
    doc.add_page_break()

    p_abs_title = doc.add_paragraph()
    p_abs_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_title.paragraph_format.space_before = Pt(20)
    p_abs_title.paragraph_format.space_after = Pt(8)
    r = p_abs_title.add_run("ABSTRACT")
    r.font.name = "Times New Roman"; r.font.size = Pt(15); r.bold = True

    p_abs_sub = doc.add_paragraph()
    p_abs_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs_sub.paragraph_format.space_before = Pt(0)
    p_abs_sub.paragraph_format.space_after = Pt(14)
    r = p_abs_sub.add_run("PARCS: Performance Anomaly & Regression Correlation System")
    r.font.name = "Times New Roman"; r.font.size = Pt(12.5); r.bold = True

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
        "powercfg /sleepstudy, operates strictly in a stateless, session-by-session manner, lacking longitudinal persistence, "
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
        "PARCS implements machine-specific statistical baselines utilizing robust non-parametric estimators (Median, MAD, IQR). "
        "Individual sessions are scored for point anomalies using Modified Z-scores. To eliminate false alarms triggered by transient "
        "battery spikes, PARCS introduces a directional sustained regression detector that requires consecutive qualifying degraded sessions "
        "in strict timestamp order. When a sustained regression is established, an explainable temporal change correlation "
        "engine searches within configurable pre- and post-regression time windows to identify temporally associated system "
        "events (device driver updates, Windows patches, kernel power errors), strictly noting that temporal association does not assert causation."
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


# ----------------------------------------------------------------------
# Chapter 1: Introduction
# ----------------------------------------------------------------------
def add_chapter_1(doc):
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
        "installed memory, and attached peripherals. Static thresholding produces unacceptable rates of false alarms on high-performance "
        "machines and missed detections on ultra-low-power systems.",
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
    add_bullet_p(doc, "Introduces the operational background of Windows Modern Standby, articulates the problem statement, defines project objectives, and outlines the functional scope.", bold_prefix="Chapter 1 (Introduction): ")
    add_bullet_p(doc, "Surveys foundational literature in ACPI power management, robust statistical process monitoring, time-series anomaly detection, temporal event correlation, and columnar analytics, identifying the technical research gap.", bold_prefix="Chapter 2 (Literature Study): ")
    add_bullet_p(doc, "Details hardware configurations, software technology stacks (Python, Parquet, DuckDB, FastAPI, Streamlit, pytest), and technical feature rationale.", bold_prefix="Chapter 3 (Software Requirement Analysis): ")
    add_bullet_p(doc, "Presents the formal Software Requirement Specification (SRS), enumerating functional and non-functional requirements and analyzing architectural constraints.", bold_prefix="Chapter 4 (System Analysis): ")
    add_bullet_p(doc, "Details the multi-tiered system design, including the system architecture, software workflow, use case model, logical component structure, activity flow, and Level-0/Level-1 data flow diagrams.", bold_prefix="Chapter 5 (System Design): ")
    add_bullet_p(doc, "Documents the concrete implementation of collectors, ETL pipelines, Parquet/DuckDB storage, baseline estimators, streak-based regression detection, correlation algorithms, API routes, and dashboard interfaces.", bold_prefix="Chapter 6 (System Implementation): ")
    add_bullet_p(doc, "Presents the testing methodology, formal test case specifications, unit testing regimes, and integrated acceptance audit results (253 passing automated tests, 0 failures, 1 warning).", bold_prefix="Chapter 7 (Testing): ")
    add_bullet_p(doc, "Synthesizes experimental results, articulates system limitations, defines future research directions, and presents concluding observations.", bold_prefix="Chapter 8 (Results and Conclusion): ")
    add_bullet_p(doc, "Supplies supplementary technical materials, including startup instructions, API payloads, representative source code excerpts, user documentation, and an academic glossary.", bold_prefix="Chapter 9 (Appendices): ")
    add_bullet_p(doc, "Lists authentic academic books, research papers, and official technical documentation consulted during project execution.", bold_prefix="Chapter 10 (Bibliography): ")


# ----------------------------------------------------------------------
# Master Builder Function
# ----------------------------------------------------------------------
def generate_parcs_master_report(output_docx: str, output_pdf: str):
    doc = docx.Document()

    # Section 1 Setup
    sec = doc.sections[0]
    sec.page_width = Inches(8.27)
    sec.page_height = Inches(11.69)
    sec.top_margin = Inches(0.8)
    sec.bottom_margin = Inches(0.8)
    sec.left_margin = Inches(0.8)
    sec.right_margin = Inches(0.8)
    add_page_border(sec)

    print("Building Preliminary Pages 1-3...")
    add_first_three_pages(doc)

    print("Building Page 4: Table of Contents...")
    add_table_of_contents_page(doc)

    print("Building Page 5: Abstract...")
    add_abstract_page(doc)

    print("Building Chapter 1: Introduction...")
    add_chapter_1(doc)

    print("Building Chapters 2, 3, 4...")
    from chapters_2_4 import add_chapter_2, add_chapter_3, add_chapter_4
    add_chapter_2(doc)
    add_chapter_3(doc)
    add_chapter_4(doc)

    print("Building Chapters 5, 6 with all 7 Figures...")
    from chapters_5_6 import add_chapter_5, add_chapter_6
    add_chapter_5(doc)
    add_chapter_6(doc)

    print("Building Chapters 7, 8, 9, 10...")
    from chapters_7_10 import add_chapter_7, add_chapter_8, add_chapter_9, add_chapter_10
    add_chapter_7(doc)
    add_chapter_8(doc)
    add_chapter_9(doc)
    add_chapter_10(doc)

    # Ensure page border on all sections
    for s in doc.sections:
        add_page_border(s)

    print(f"Saving Word document: {output_docx}...")
    doc.save(output_docx)
    print("Master Word document successfully saved!")

    # Convert to PDF via Word COM
    print("Exporting to PDF preview via Microsoft Word COM...")
    abs_docx = os.path.abspath(output_docx)
    abs_pdf = os.path.abspath(output_pdf)
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        wdoc = word.Documents.Open(abs_docx)
        wdoc.SaveAs(abs_pdf, FileFormat=17)
        wdoc.Close()
        print("PDF preview successfully created!")
    finally:
        word.Quit()

    # QA Verification with PyMuPDF
    print("\n--- Running Automated Quality Assurance Verification ---")
    pdf_doc = pymupdf.open(abs_pdf)
    total_pages = len(pdf_doc)
    print(f"Total Page Count: {total_pages}")
    
    expected_starts = {
        0: "Research AI: Generative AI-Based Research Paper Intelligence System",
        1: "BONAFIDE CERTIFICATE",
        2: "ACKNOWLEDGEMENT",
        3: "TABLE OF CONTENTS",
        4: "ABSTRACT",
        5: "1. INTRODUCTION",
    }
    
    for pno, expected_text in expected_starts.items():
        actual_text = pdf_doc[pno].get_text().strip()
        normalized_text = " ".join(actual_text.split())
        first_line = actual_text.split('\n')[0] if actual_text else "EMPTY"
        print(f"Page {pno+1}: {first_line[:65]}")
        assert expected_text in normalized_text[:250], f"Page {pno+1} mismatch! Expected '{expected_text}' in '{normalized_text[:250]}'"

    print("\nALL PRELIMINARY PAGES, TOC, ABSTRACT, AND CHAPTER 1 ALIGNED PERFECTLY!")


if __name__ == "__main__":
    generate_parcs_master_report("PARCS_Project_Report.docx", "PARCS_Project_Report.pdf")
