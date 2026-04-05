import fitz  # PyMuPDF

doc = fitz.open("ลักทรัพย์.pdf")

for page in doc:
    text_instances = page.search_for("สมชาย")

    for inst in text_instances:
        page.add_redact_annot(inst, fill=(0,0,0))

    page.apply_redactions()

doc.save("output_redacted.pdf")