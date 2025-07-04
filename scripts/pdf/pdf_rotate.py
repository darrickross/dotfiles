import os
import PyPDF2

# Path to your PDF file
directory = "/mnt/c/Users/ItsJustMech/Desktop"
pdf_path = f"{directory}/Manual-SideTable-Yaheetech.pdf"

# base, ext = os.path.splitext(pdf_path)
# output_path = f"{base}-new{ext}"
output_path = pdf_path

# Pages to rotate (0-based indexing)
# pages_to_rotate = [1, 2, 3, 5]  # corresponds to pages 2, 3, 4, and 6
pages_to_rotate = [
    1,
    0,
    3,
    2,
    5,
    4,
    7,
    6,
    # 8,
    # 9,
    # 10,
]  # corresponds to pages 2, 3, 4, and 6

with open(pdf_path, "rb") as file:
    reader = PyPDF2.PdfReader(file)
    writer = PyPDF2.PdfWriter()

    for i, page in enumerate(reader.pages):
        if i in pages_to_rotate:
            page.rotate(90)  # Rotate 90 degrees clockwise
        writer.add_page(page)

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

print(f"Rotated pages saved to {output_path}")
