import subprocess
import os

def convert_docx_to_pdf(docx_path: str) -> str:
    output_dir = os.path.dirname(docx_path)

    subprocess.run([
        "libreoffice",
        "--headless",
        "--convert-to", "pdf",
        docx_path,
        "--outdir", output_dir
    ], check=True)

    pdf_path = docx_path.replace(".docx", ".pdf")
    return pdf_path