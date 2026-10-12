import pymupdf

doc = pymupdf.open(r"C:\Users\shant\Downloads\Research AI Report 2.pdf")
for pno in range(3):
    page = doc[pno]
    print(f"\n=================== PAGE {pno+1} ===================")
    for b in page.get_text("dict")["blocks"]:
        if "lines" in b:
            bbox = b["bbox"]
            full_text = " ".join([span["text"] for line in b["lines"] for span in line["spans"]]).strip()
            print(f"y0={bbox[1]:.1f}, y1={bbox[3]:.1f}, text: {full_text[:70]}")
