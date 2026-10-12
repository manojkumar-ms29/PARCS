import docx
from docx.oxml import parse_xml
from docx.shared import Inches, Pt, RGBColor
import win32com.client
import os

doc = docx.Document()
section = doc.sections[0]
section.page_width = Inches(8.27)  # A4
section.page_height = Inches(11.69)
section.top_margin = Inches(1)
section.bottom_margin = Inches(1)
section.left_margin = Inches(1)
section.right_margin = Inches(1)

# Add page border
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

p = doc.add_paragraph("Test Paragraph inside border")
doc.save("scratch/test_border.docx")

# Convert to PDF using Word COM
word = win32com.client.Dispatch("Word.Application")
word.Visible = False
in_file = os.path.abspath("scratch/test_border.docx")
out_file = os.path.abspath("scratch/test_border.pdf")
doc_word = word.Documents.Open(in_file)
doc_word.SaveAs(out_file, FileFormat=17)
doc_word.Close()
word.Quit()
print("Successfully generated and converted test_border.pdf")
