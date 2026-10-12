import pymupdf

doc = pymupdf.open(r"C:\Users\shant\Downloads\Research AI Report 2.pdf")
for pno in range(3):
    page = doc[pno]
    print(f"=== PAGE {pno+1} RECT: {page.rect} ===")
    blocks = page.get_text("dict")["blocks"]
    for b in blocks:
        if "lines" in b:
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        print(f"font={span['font']}, size={span['size']:.1f}, flags={span['flags']}, text={text[:60]}")
