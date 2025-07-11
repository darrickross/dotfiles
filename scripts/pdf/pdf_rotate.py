import os
import argparse
import sys
import PyPDF2


def process_pdfs(directory):
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
    total_files = len(pdf_files)

    if total_files == 0:
        print("No PDF files found in the directory.")
        return

    # Determine padding width for file indices
    file_pad = len(str(total_files))

    for file_idx, pdf_file in enumerate(pdf_files, start=1):
        prompt = f"[{file_idx:0{file_pad}}/{total_files}] Do you want to process '{pdf_file}'? (y/n, Enter to skip): "
        sys.stdout.write(prompt)
        sys.stdout.flush()
        answer = input().strip().lower()
        if answer not in ("y", "yes"):
            skip_msg = f"Skipped '{pdf_file}'"
            clear_line = "\r" + " " * len(prompt) + "\r" + skip_msg + "\n"
            sys.stdout.write(clear_line)
            sys.stdout.flush()
            continue

        input_path = os.path.join(directory, pdf_file)
        with open(input_path, "rb") as in_f:
            reader = PyPDF2.PdfReader(in_f)
            writer = PyPDF2.PdfWriter()

            total_pages = len(reader.pages)
            page_pad = len(str(total_pages))

            for page_idx, page in enumerate(reader.pages, start=1):
                page_prompt = (
                    f"\t[{page_idx:0{page_pad}}/{total_pages}] "
                    "Rotate 90/180/270 or skip (blank = skip)? "
                )
                while True:
                    user_input = input(page_prompt).strip()
                    if user_input in ("", "skip", "s"):
                        break
                    elif user_input in ("90", "9"):
                        page.rotate(90)
                        break
                    elif user_input in ("180", "18"):
                        page.rotate(180)
                        break
                    elif user_input in ("270", "27"):
                        page.rotate(270)
                        break
                    else:
                        print(
                            "\tInvalid input. Please enter 90/180/270, skip, or blank to skip."
                        )

                writer.add_page(page)

        # Write the rotated PDF back out (overwriting original)
        with open(input_path, "wb") as out_f:
            writer.write(out_f)

        updated_msg = f"Updated '{pdf_file}'"
        clear_line = "\r" + " " * len(prompt) + "\r" + updated_msg + "\n"
        sys.stdout.write(clear_line)
        sys.stdout.flush()

    print("\nAll done.")


def main():
    parser = argparse.ArgumentParser(
        description="Rotate pages in PDF files interactively.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-f", "--folder", required=True, help="Path to the folder containing PDF files."
    )

    args = parser.parse_args()
    directory = args.folder

    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a valid directory.")
        return

    process_pdfs(directory)


if __name__ == "__main__":
    main()
