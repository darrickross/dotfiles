import os
import PyPDF2

# Path to your PDF file
directory = "/mnt/c/Users/ItsJustMech/Desktop"
pdf_path = f"{directory}/Bill-Verizon-20250523.pdf"

# You can overwrite the input file or change this to output a new file
output_path = pdf_path  # Or use: f"{os.path.splitext(pdf_path)[0]}-reordered.pdf"

# Define the new page order (0-based indexing)
# Example: reverse the first 8 pages
new_page_order = [
    2,
    3,
    0,
    1,
    # Add more indices if needed
]

with open(pdf_path, "rb") as file:
    reader = PyPDF2.PdfReader(file)
    writer = PyPDF2.PdfWriter()

    for i in new_page_order:
        if i < len(reader.pages):
            writer.add_page(reader.pages[i])
        else:
            print(f"Warning: Page index {i} is out of range")

    with open(output_path, "wb") as output_file:
        writer.write(output_file)

print(f"Reordered PDF saved to {output_path}")
