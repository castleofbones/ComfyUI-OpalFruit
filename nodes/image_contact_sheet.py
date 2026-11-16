"""V3 node wrapper for the PIL-only image contact-sheet engine."""

from comfy_api.latest import io

from .contact_sheet import build_contact_sheet


class ImageContactSheet(io.ComfyNode):
    """Generate a contact sheet of image thumbnails from a directory of files."""

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
        output = build_contact_sheet(
            image_directory,
            filename_pattern=filename_pattern,
            columns=columns,
            thumbnail_width=thumbnail_width,
            show_labels=show_labels,
            background_colour=background_colour,
            output_filename=output_filename,
        )
        return io.NodeOutput(str(output))
