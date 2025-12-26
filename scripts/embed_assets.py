"""
Script to convert assets folder to embedded base64 Python file.

Usage:
    python scripts/embed_assets.py

This reads from `assets/` folder and generates `src/embedded_assets.py`

Folder structure expected:
    assets/
    ├── sequence-name-1/
    │   ├── action-1.png
    │   └── action-2.png
    └── sequence-name-2/
        ├── action-1.png
        ├── action-2.png
        └── action-3.png
"""

import base64
from pathlib import Path


def embed_assets(
    assets_folder: str = "assets",
    output_file: str = "src/embedded_assets.py",
) -> None:
    """Convert assets folder to embedded Python file."""
    assets_path = Path(assets_folder)
    output_path = Path(output_file)

    if not assets_path.exists():
        print(f"Error: Assets folder not found: {assets_folder}")
        print("Please create the assets folder with your image sequences.")
        return

    assets_dict: dict[str, dict[str, str]] = {}
    total_images = 0

    # Process each subfolder
    for subfolder in sorted(assets_path.iterdir()):
        if not subfolder.is_dir():
            continue

        sequence_name = subfolder.name
        actions: dict[str, str] = {}

        # Process each PNG in the subfolder
        png_files = sorted(subfolder.glob("*.png"))
        if not png_files:
            print(f"  Skipping '{sequence_name}': no PNG files")
            continue

        for png_file in png_files:
            action_name = png_file.stem

            # Read and encode the image
            with open(png_file, "rb") as f:
                image_bytes = f.read()
            base64_string = base64.b64encode(image_bytes).decode("utf-8")

            actions[action_name] = base64_string
            total_images += 1

        assets_dict[sequence_name] = actions
        print(f"  Embedded '{sequence_name}': {len(actions)} action(s)")

    if not assets_dict:
        print("No valid sequences found in assets folder.")
        return

    # Generate the Python file
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write('"""\n')
        f.write("Auto-generated file containing embedded image assets as base64 strings.\n")
        f.write("\n")
        f.write("DO NOT EDIT MANUALLY - Run `python scripts/embed_assets.py` to regenerate.\n")
        f.write('"""\n\n')
        f.write("ASSETS: dict[str, dict[str, str]] = {\n")

        for sequence_name, actions in assets_dict.items():
            f.write(f'    "{sequence_name}": {{\n')
            for action_name, base64_data in actions.items():
                # Split long base64 strings for readability (optional)
                f.write(f'        "{action_name}": "{base64_data}",\n')
            f.write("    },\n")

        f.write("}\n")

    print(f"\nGenerated: {output_path}")
    print(f"Total: {len(assets_dict)} sequence(s), {total_images} image(s)")


if __name__ == "__main__":
    print("Embedding assets...\n")
    embed_assets()
