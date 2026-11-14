from pathlib import Path
import tempfile
import unittest

from PIL import Image

from nodes.image_contact_sheet import ImageContactSheet, filename_label


class ImageContactSheetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.node = ImageContactSheet()

    def image(self, name, size=(20, 20), colour="red", mode="RGB"):
        path = self.directory / name
        Image.new(mode, size, colour).save(path)
        return path

    def create(self, **kwargs):
        options = {"columns": 2, "thumbnail_width": 20, "show_labels": False}
        options.update(kwargs)
        return Path(self.node.create(str(self.directory), **options)[0])

    def test_sorted_grid_aspect_ratio_and_sources_unchanged(self):
        paths = [
            self.image("c.png", colour="blue"),
            self.image("a.png", size=(40, 20), colour="red"),
            self.image("b.png", size=(20, 40), colour="lime"),
        ]
        original = {path: path.read_bytes() for path in paths}
        output = self.create(background_colour="#808080")
        self.assertTrue(output.is_absolute())
        with Image.open(output) as sheet:
            self.assertEqual(sheet.size, (40, 40))
            self.assertEqual(sheet.getpixel((10, 0)), (128, 128, 128))
            self.assertEqual(sheet.getpixel((10, 10)), (255, 0, 0))
            self.assertEqual(sheet.getpixel((20, 10)), (128, 128, 128))
            self.assertEqual(sheet.getpixel((30, 10)), (0, 255, 0))
            self.assertEqual(sheet.getpixel((10, 30)), (0, 0, 255))
            self.assertEqual(sheet.getpixel((30, 30)), (128, 128, 128))
        self.assertEqual(original, {path: path.read_bytes() for path in paths})

    def test_rgba_alpha_compositing(self):
        self.image("half.png", colour=(255, 0, 0, 128), mode="RGBA")
        self.image("transparent.png", colour=(0, 255, 0, 0), mode="RGBA")
        with Image.open(self.create(background_colour="#0000ff")) as sheet:
            self.assertEqual(sheet.mode, "RGB")
            self.assertEqual(sheet.getpixel((10, 10)), (128, 0, 127))
            self.assertEqual(sheet.getpixel((30, 10)), (0, 0, 255))

    def test_labels_and_configured_column_count(self):
        self.image("happy_00001_.png")
        with Image.open(self.create(columns=4, thumbnail_width=80, show_labels=True)) as sheet:
            self.assertEqual(sheet.size, (320, 104))
            label = sheet.crop((0, 80, 80, 104))
            self.assertGreater(len(label.getcolors()), 1)

    def test_filename_labels(self):
        for name, expected in (
            ("happy_00001_.png", "happy"),
            ("happy_00001.png", "happy"),
            ("a_b_12345_.PNG", "a_b"),
            ("happy.png", "happy"),
            ("version2.png", "version2"),
            ("happy_12_extra.png", "happy_12_extra"),
        ):
            with self.subTest(name=name):
                self.assertEqual(filename_label(name), expected)

    def test_empty_directory_and_excluded_output(self):
        with self.assertRaisesRegex(ValueError, "No source images"):
            self.create()
        self.image("contact-sheet.png")
        with self.assertRaisesRegex(ValueError, "No source images"):
            self.create()
        self.image("source.png")
        for _ in range(2):
            with Image.open(self.create(columns=1)) as sheet:
                self.assertEqual(sheet.size, (20, 20))

    def test_custom_output_and_pattern(self):
        self.image("source.jpg")
        self.image("ignored.png")
        with Image.open(self.create(filename_pattern="*.jpg", output_filename="custom.png")) as sheet:
            self.assertEqual(sheet.size, (40, 20))
            self.assertEqual(Path(sheet.filename).name, "custom.png")

    def test_unreadable_image_is_named_and_nothing_is_written(self):
        bad = self.directory / "broken.png"
        bad.write_bytes(b"not an image")
        with self.assertRaisesRegex(ValueError, "Cannot read image.*broken.png"):
            self.create()
        self.assertFalse((self.directory / "contact-sheet.png").exists())

    def test_invalid_inputs(self):
        self.image("source.png")
        for options in (
            {"columns": 0}, {"columns": True}, {"thumbnail_width": -1},
            {"thumbnail_width": 1.5}, {"background_colour": "not a colour"},
            {"background_colour": "#ffffff00"},
            {"output_filename": "../source.png"}, {"output_filename": "sheet.jpg"},
            {"filename_pattern": "../*.png"}, {"filename_pattern": ""},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.create(**options)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            self.node.create(str(self.directory / "missing"))

    def test_output_cannot_overwrite_source_via_link(self):
        source = self.image("source.png")
        output = self.directory / "contact-sheet.png"
        output.symlink_to(source)
        original = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            self.create()
        output.unlink()
        output.hardlink_to(source)
        with self.assertRaisesRegex(ValueError, "aliases"):
            self.create()
        self.assertEqual(source.read_bytes(), original)

    def test_disk_changes_are_not_cached(self):
        token = self.node.IS_CHANGED(image_directory=str(self.directory))
        self.assertNotEqual(token, token)
        self.assertTrue(self.node.OUTPUT_NODE)


if __name__ == "__main__":
    unittest.main()
