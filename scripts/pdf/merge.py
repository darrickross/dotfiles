#!/usr/bin/env python3

import os
import re
import argparse
from PyPDF2 import PdfMerger

def parse_args():
    parser = argparse.ArgumentParser(description="Merge grouped PDFs in a folder.")
    parser.add_argument(
        "-f", "--folder",
        help="Folder containing the PDF files. If not provided, you'll be prompted.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Automatically merge all groups without asking which to skip.",
    )
    return parser.parse_args()

def get_input_folder(arg_folder):
    if arg_folder:
        return arg_folder
    return input("Enter the folder path containing the PDFs: ").strip()

def find_pdf_groups(folder):
    pattern = re.compile(r"^(.*?)\s\((\d+)\)\.pdf$")
    grouped = {}

    for file in os.listdir(folder):
        if file.endswith('.pdf'):
            match = pattern.match(file)
            if match:
                prefix = match.group(1)
                grouped.setdefault(prefix, []).append((int(match.group(2)), os.path.join(folder, file)))

    return grouped

def ask_user_which_to_skip(groups):
    print("Found the following PDF groups:")
    for group, files in groups.items():
        print(f" - {group}: {len(files)} files")

    skip = input("Enter any group names to skip (comma-separated), or press Enter to continue: ").strip()
    to_skip = set(map(str.strip, skip.split(','))) if skip else set()
    return {k: v for k, v in groups.items() if k not in to_skip}

def merge_pdfs(groups, folder):
    for prefix, files in groups.items():
        merger = PdfMerger()
        for _, filepath in sorted(files):  # sort by extracted number
            merger.append(filepath)
        output_path = os.path.join(folder, f"{prefix}.pdf")
        merger.write(output_path)
        merger.close()
        print(f"Merged {len(files)} files into: {output_path}")

def main():
    args = parse_args()
    folder = get_input_folder(args.folder)

    if not os.path.isdir(folder):
        print(f"Invalid folder path: {folder}")
        return

    groups = find_pdf_groups(folder)
    if not groups:
        print("No matching PDF groups found.")
        return

    if not args.yes:
        groups = ask_user_which_to_skip(groups)
        if not groups:
            print("No groups selected for merging.")
            return

    merge_pdfs(groups, folder)

if __name__ == "__main__":
    main()
