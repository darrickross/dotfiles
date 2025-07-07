from PIL import Image
import os


def convert_each_image_to_pdf(input_folder, output_folder):
    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff")):
            input_path = os.path.join(input_folder, filename)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_folder, f"{base_name}.pdf")

            img = Image.open(input_path)

            # Handle multi-page TIFFs
            if (
                filename.lower().endswith((".tif", ".tiff"))
                and getattr(img, "n_frames", 1) > 1
            ):
                frames = []
                for i in range(img.n_frames):
                    img.seek(i)
                    frame = img.convert("RGB")
                    frames.append(frame)
                frames[0].save(output_path, save_all=True, append_images=frames[1:])
            else:
                # Convert to RGB if needed
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(output_path, "PDF")

            print(f"Converted {filename} → {output_path}")


# Example usage:
input_dir = "/mnt/c/Users/ItsJustMech/Desktop/temp"
output_dir = "/mnt/c/Users/ItsJustMech/Desktop/temp"
convert_each_image_to_pdf(input_dir, output_dir)
