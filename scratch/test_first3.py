import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn
import win32com.client
import os

def create_first_three_pages_test():
    doc = docx.Document()
    
    # Page setup - A4
    section = doc.sections[0]
    section.page_width = Inches(8.27)
    section.page_height = Inches(11.69)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    
    # Page borders
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

    # PAGE 1: COVER
    # Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(12)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.line_spacing = 1.15
    run = p_title.add_run("Research AI: Generative AI-Based Research Paper Intelligence System")
    run.font.name = "Times New Roman"
    run.font.size = Pt(16)
    run.bold = True

    # Submitted to
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(4)
    run = p_sub.add_run("A Project report submitted to the")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    # Department
    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_dept.paragraph_format.space_before = Pt(0)
    p_dept.paragraph_format.space_after = Pt(4)
    run = p_dept.add_run("DEPARTMENT OF COMPUTER APPLICATIONS")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.bold = True

    # Partial fulfilment
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

    # Degree
    p_deg = doc.add_paragraph()
    p_deg.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_deg.paragraph_format.space_before = Pt(0)
    p_deg.paragraph_format.space_after = Pt(14)
    run = p_deg.add_run("BACHELOR OF COMPUTER APPLICATIONS (HONOURS) IN DS")
    run.font.name = "Times New Roman"
    run.font.size = Pt(13)
    run.bold = True

    # By
    p_by = doc.add_paragraph()
    p_by.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_by.paragraph_format.space_before = Pt(0)
    p_by.paragraph_format.space_after = Pt(14)
    run = p_by.add_run("By")
    run.font.name = "Times New Roman"
    run.font.size = Pt(14)
    run.italic = True

    # Student Name & Reg No
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

    # Guidance
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

    # SRM Logo
    p_logo = doc.add_paragraph()
    p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_logo.paragraph_format.space_before = Pt(0)
    p_logo.paragraph_format.space_after = Pt(14)
    from PIL import Image
    with Image.open("scratch/srm_logo.png") as img:
        img.save("scratch/srm_logo_fixed.png", "PNG", dpi=(300, 300))
    run_logo = p_logo.add_run()
    run_logo.add_picture("scratch/srm_logo_fixed.png", width=Inches(3.3))

    # University info
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

    # PAGE 2: BONAFIDE CERTIFICATE
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

    # Table for Guide and HOD
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

    # Table for Examiners
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

    # Page 4: TOC placeholder to see pagination
    doc.add_page_break()
    p_toc = doc.add_paragraph()
    p_toc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_toc.add_run("TABLE OF CONTENTS")
    r.font.name = "Times New Roman"; r.font.size = Pt(16); r.bold = True

    doc.save("scratch/test_first3.docx")
    print("Saved test_first3.docx")

if __name__ == "__main__":
    create_first_three_pages_test()
    # Convert to PDF and check page count
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    in_file = os.path.abspath("scratch/test_first3.docx")
    out_file = os.path.abspath("scratch/test_first3.pdf")
    doc_word = word.Documents.Open(in_file)
    doc_word.SaveAs(out_file, FileFormat=17)
    doc_word.Close()
    word.Quit()
    print("Converted test_first3.pdf")
