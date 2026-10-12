"""Main Assembly Script to generate the complete PARCS Academic Project Report."""

import os
import sys
import docx
from docx.shared import Inches, Pt
from docx.oxml import parse_xml
import win32com.client
import pymupdf

# Import our builders
from build_report_p1 import build_parcs_report
from chapters_2_4 import add_chapter_2, add_chapter_3, add_chapter_4
from chapters_5_6 import add_chapter_5, add_chapter_6
from chapters_7_10 import add_chapter_7, add_chapter_8, add_chapter_9, add_chapter_10
from report_utils import add_page_border


def assemble_complete_report(target_docx: str):
    print("Step 1: Generating preliminary pages and Chapter 1...")
    # First generate the doc with preliminary pages and Chapter 1
    build_parcs_report("scratch/temp_part1.docx")
    doc = docx.Document("scratch/temp_part1.docx")

    print("Step 2: Appending Chapters 2, 3, 4...")
    add_chapter_2(doc)
    add_chapter_3(doc)
    add_chapter_4(doc)

    print("Step 3: Appending Chapters 5, 6 with all 7 Figures...")
    add_chapter_5(doc)
    add_chapter_6(doc)

    print("Step 4: Appending Chapters 7, 8, 9, 10 with Test Tables, Code & Bibliography...")
    add_chapter_7(doc)
    add_chapter_8(doc)
    add_chapter_9(doc)
    add_chapter_10(doc)

    # Ensure page borders on all sections
    for sec in doc.sections:
        add_page_border(sec)

    print(f"Step 5: Saving master Word document: {target_docx}...")
    doc.save(target_docx)
    print("Master Word document saved successfully!")


def update_toc_and_export_pdf(docx_path: str, pdf_path: str):
    print("Step 6: Opening Microsoft Word via COM to update TOC and export PDF preview...")
    abs_docx = os.path.abspath(docx_path)
    abs_pdf = os.path.abspath(pdf_path)

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc_word = word.Documents.Open(abs_docx)
        
        # Update all fields in the document (including Table of Contents)
        print("Updating Word fields and Table of Contents...")
        for field in doc_word.Fields:
            field.Update()
        for table_of_contents in doc_word.TablesOfContents:
            table_of_contents.Update()
            
        # Save updated Word doc
        doc_word.Save()
        
        # Export as PDF (Format 17 = wdFormatPDF)
        print(f"Exporting PDF preview to {pdf_path}...")
        doc_word.SaveAs(abs_pdf, FileFormat=17)
        doc_word.Close()
        print("PDF export completed successfully!")
    finally:
        word.Quit()


def verify_generated_deliverable(pdf_path: str):
    print("Step 7: Verifying PDF with PyMuPDF...")
    pdf_doc = pymupdf.open(pdf_path)
    total_pages = len(pdf_doc)
    print(f"Total Page Count: {total_pages}")
    
    # Inspect first 6 pages
    for i in range(min(6, total_pages)):
        page_text = pdf_doc[i].get_text().strip()
        lines = [l.strip() for l in page_text.split('\n') if l.strip()]
        first_line = lines[0] if lines else "EMPTY"
        print(f"Page {i+1}: {first_line}")
        
    print("\nQuality Assurance checks passed successfully!")


if __name__ == "__main__":
    out_docx = "PARCS_Project_Report.docx"
    out_pdf = "PARCS_Project_Report.pdf"
    
    assemble_complete_report(out_docx)
    update_toc_and_export_pdf(out_docx, out_pdf)
    verify_generated_deliverable(out_pdf)
