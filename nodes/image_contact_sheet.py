"""Generate a contact sheet from images on disk, using only PIL for image processing."""

from pathlib import Path
import re

from PIL import Image, ImageColor, ImageDraw, ImageOps

from comfy_api.latest import io


def filename_label(filename):
    return re.sub(r"_\d+_?$", "", Path(filename).stem)


class ImageContactSheet(io.ComfyNode):
    """Generate a contact sheet of image thumbnails from a directory of files."""

    LABEL_HEIGHT = 24

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="OpalFruitImageContactSheet",
            display_name="Image Contact Sheet",
            category="OpalFruit/Image",
            description="Generate a contact sheet of image thumbnails from a directory of files.",
            inputs=[
                io.String.Input("image_directory", default=""),
                io.String.Input("filename_pattern", default="*.png"),
                io.Int.Input("columns", default=4, min=1),
                io.Int.Input("thumbnail_width", default=256, min=1),
                io.Boolean.Input("show_labels", default=True),
                io.String.Input("background_colour", default="#808080"),
                io.String.Input("output_filename", default="contact-sheet.png"),
                io.AnyType.Input(
                    "trigger",
                    optional=True,
                    tooltip="Optional dependency. Connect End Loop 'outputs' to run after a Start Loop / End Loop completes. The value is ignored during image processing.",
                ),
            ],
            outputs=[io.String.Output(display_name="output_path")],
            is_output_node=True,
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        # Source files may change without any widget values changing.
        return float("nan")

    @classmethod
    def execute(
        cls,
        image_directory,
        filename_pattern="*.png",
        columns=4,
        thumbnail_width=256,
        show_labels=True,
        background_colour="#808080",
        output_filename="contact-sheet.png",
        trigger=None,
    ) -> io.NodeOutput:
        # The trigger is an execution-order dependency only (e.g. End Loop
        # "outputs"). It is intentionally ignored here; image processing is
        # independent of the value it carries.
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
        cell_height = thumbnail_width + (cls.LABEL_HEIGHT if show_labels else 0)
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
        return io.NodeOutput(str(output))
