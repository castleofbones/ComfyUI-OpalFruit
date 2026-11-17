"""Generate a contact sheet from images on disk, using only PIL for image processing."""

from pathlib import Path
import re

from PIL import Image, ImageColor, ImageDraw, ImageOps


LABEL_HEIGHT = 24


def filename_label(filename):
    return re.sub(r"_\d+_?$", "", Path(filename).stem)


def build_contact_sheet(
    image_directory,
    filename_pattern="*.png",
    columns=4,
    thumbnail_width=256,
    show_labels=True,
    background_colour="#808080",
    output_filename="contact-sheet.png",
) -> Path:
    """Stitch the matching images in a directory into a single labelled PNG grid.

    Returns the absolute path of the written sheet. Raises ``ValueError`` for
    invalid inputs or when a sheet cannot be read or written.
    """
    directory = Path(image_directory).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError(f"Image directory does not exist: {directory}")
    for name, value in (("columns", columns), ("thumbnail_width", thumbnail_width)):
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer.")
    if (
        not output_filename
        or Path(output_filename).name != output_filename
        or Path(output_filename).suffix.lower() != ".png"
    ):
        raise ValueError("Output filename must be a plain .png filename.")
    output = directory / output_filename
    if output.is_symlink():
        raise ValueError("Output file must not be a symbolic link.")
    try:
        background = ImageColor.getrgb(background_colour)
        if len(background) != 3:
            raise ValueError("Background must be opaque.")
    except (ValueError, TypeError) as exc:
        raise ValueError("Background colour must be a valid opaque colour.") from exc
    if (
        not filename_pattern
        or "/" in filename_pattern
        or "\\" in filename_pattern
    ):
        raise ValueError("Filename pattern must be a nonempty filename glob.")
    paths = sorted(
        path for path in directory.glob(filename_pattern)
        if path.is_file() and path != output
    )
    if not paths:
        raise ValueError(f"No source images match '{filename_pattern}' in {directory}.")
    thumbnails = []
    for path in paths:
        if output.exists() and path.samefile(output):
            raise ValueError(f"Source image aliases the output file: {path}")
        try:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail(
                    (thumbnail_width, thumbnail_width), Image.Resampling.LANCZOS
                )
                thumbnails.append(image)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ValueError(f"Cannot read image '{path}': {exc}") from exc
    cell_height = thumbnail_width + (LABEL_HEIGHT if show_labels else 0)
    rows = (len(paths) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * thumbnail_width, rows * cell_height), background)
    text_colour = "black" if sum(background) > 382 else "white"
    for index, (path, image) in enumerate(zip(paths, thumbnails)):
        cell = Image.new("RGBA", (thumbnail_width, cell_height), background + (255,))
        cell.alpha_composite(
            image,
            ((thumbnail_width - image.width) // 2, (thumbnail_width - image.height) // 2),
        )
        if show_labels:
            draw = ImageDraw.Draw(cell)
            label = filename_label(path.name)
            text_width = draw.textlength(label)
            x = (thumbnail_width - text_width) // 2
            # Keep the label inside its own cell: centre when it fits, otherwise
            # left-align at the cell edge so no part crosses into a neighbour.
            if x < 0:
                x = 0
            draw.text((x, thumbnail_width + 4), label, fill=text_colour)
        sheet.paste(cell.convert("RGB"), (
            (index % columns) * thumbnail_width, (index // columns) * cell_height
        ))
    try:
        sheet.save(output, format="PNG")
    except OSError as exc:
        raise ValueError(f"Cannot save contact sheet '{output}': {exc}") from exc
    return output
