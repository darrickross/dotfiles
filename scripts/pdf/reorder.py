import argparse

import PyPDF2


def main():
    parser = argparse.ArgumentParser(description="Reorder pages in a PDF file")
    parser.add_argument("input", help="Input PDF file path")
    parser.add_argument(
        "-o",
        "--output",
        help="Output PDF file path (default: overwrite input)",
    )
    parser.add_argument(
        "page_order",
        nargs="+",
        type=int,
        metavar="PAGE",
        help="New page order as 0-based indices (e.g. 2 3 0 1)",
    )
    args = parser.parse_args()

    output_path = args.output or args.input

    with open(args.input, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        writer = PyPDF2.PdfWriter()

        for i in args.page_order:
            if i < len(reader.pages):
                writer.add_page(reader.pages[i])
            else:
                print(f"Warning: Page index {i} is out of range")

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

    print(f"Reordered PDF saved to {output_path}")


if __name__ == "__main__":
    main()
