import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import yaml

from nodes.yaml_expressions import YAMLExpressionExtractor, YAMLExpressionLoader


class YAMLExpressionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "expressions.yaml"
        self.loader = YAMLExpressionLoader()
        self.extractor = YAMLExpressionExtractor()
        self.entries = [
            {"expression": "happy", "prompt": "A happy portrait"},
            {"expression": "sad", "prompt": "A sad portrait"},
        ]

    def write(self, data):
        self.path.write_text(yaml.safe_dump(data), encoding="utf-8")

    def test_valid_catalogue_and_list_contract(self):
        self.write({"seed": 42, "expressions": self.entries})
        entries, seed = self.loader.load(str(self.path))
        self.assertEqual(entries, self.entries)
        self.assertEqual(seed, 42)
        self.assertEqual(self.loader.OUTPUT_IS_LIST, (True, False))
        self.assertEqual(
            self.loader.RETURN_TYPES[0],
            self.extractor.INPUT_TYPES()["required"]["expression"][0],
        )
        self.assertEqual(
            [self.extractor.extract(entry) for entry in entries],
            [("happy", "A happy portrait"), ("sad", "A sad portrait")],
        )
        self.assertFalse(getattr(self.extractor, "INPUT_IS_LIST", False))

    def test_invalid_catalogues(self):
        invalid = [
            None, [], "catalogue", {},
            {"expressions": self.entries},
            {"seed": True, "expressions": self.entries},
            {"seed": 1.5, "expressions": self.entries},
            {"seed": "42", "expressions": self.entries},
            {"seed": 42},
            {"seed": 42, "expressions": []},
            {"seed": 42, "expressions": {}},
            {"seed": 42, "expressions": ["happy"]},
            {"seed": 42, "expressions": [{"expression": "happy"}]},
            {"seed": 42, "expressions": [{"prompt": "portrait"}]},
            {"seed": 42, "expressions": [{"expression": 1, "prompt": "portrait"}]},
            {"seed": 42, "expressions": [{"expression": "happy", "prompt": None}]},
        ]
        for data in invalid:
            with self.subTest(data=data):
                self.write(data)
                with self.assertRaises(ValueError):
                    self.loader.load(str(self.path))

    def test_negative_seed_rejected(self):
        self.write({"seed": -1, "expressions": self.entries})
        with self.assertRaisesRegex(ValueError, "must not be negative"):
            self.loader.load(str(self.path))
        self.write({"seed": 0, "expressions": self.entries})
        _, seed = self.loader.load(str(self.path))
        self.assertEqual(seed, 0)

    def test_empty_or_whitespace_name_and_prompt_rejected(self):
        invalid_entries = [
            {"expression": "", "prompt": "A portrait"},
            {"expression": "  ", "prompt": "A portrait"},
            {"expression": "\t", "prompt": "A portrait"},
            {"expression": "happy", "prompt": ""},
            {"expression": "happy", "prompt": "  "},
        ]
        for entry in invalid_entries:
            with self.subTest(entry=entry):
                self.write({"seed": 42, "expressions": [entry, self.entries[1]]})
                with self.assertRaisesRegex(ValueError, "must be nonempty"):
                    self.loader.load(str(self.path))

    def test_duplicate_names(self):
        self.write({"seed": 42, "expressions": [self.entries[0], self.entries[0]]})
        with self.assertRaisesRegex(ValueError, "Duplicate expression"):
            self.loader.load(str(self.path))

    def test_duplicate_names_case_insensitive(self):
        entries = [
            {"expression": "Happy", "prompt": "one"},
            {"expression": "happy", "prompt": "two"},
            {"expression": "HAPpY", "prompt": "three"},
        ]
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                with self.subTest(i=i, j=j):
                    self.write({"seed": 42, "expressions": [entries[i], entries[j]]})
                    with self.assertRaisesRegex(ValueError, "Duplicate expression"):
                        self.loader.load(str(self.path))

    def test_malformed_yaml_and_missing_file(self):
        for text in ("expressions: [", "!!python/object/apply:os.system ['echo unsafe']"):
            self.path.write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Cannot read YAML"):
                self.loader.load(str(self.path))
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, "Cannot read YAML"):
            self.loader.load(str(self.path))

    def test_content_changes_invalidate_cache_even_with_same_metadata(self):
        self.write({"seed": 42, "expressions": self.entries})
        before = self.loader.IS_CHANGED(str(self.path))
        stat = self.path.stat()
        self.path.write_text(
            self.path.read_text(encoding="utf-8").replace("happy", "jolly"),
            encoding="utf-8",
        )
        os.utime(self.path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertNotEqual(before, self.loader.IS_CHANGED(str(self.path)))
        self.assertEqual(
            self.loader.IS_CHANGED(str(self.path)), self.loader.IS_CHANGED(str(self.path))
        )
        self.path.unlink()
        self.assertNotEqual(before, self.loader.IS_CHANGED(str(self.path)))

    def test_extractor_rejects_malformed_input(self):
        for value in (None, [], "happy", {}, {"expression": "happy"},
                      {"expression": False, "prompt": "portrait"},
                      {"expression": "happy", "prompt": 5}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.extractor.extract(value)

    def test_package_registration(self):
        # Registering the package executes the V3 contact-sheet node, which
        # imports ComfyUI's ``comfy_api``. Skip when it is absent (CI).
        try:
            import comfy_api  # noqa: F401
        except ImportError:
            self.skipTest("comfy_api not available; cannot register the V3 contact-sheet node")
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "opalfruit_test_package", root / "__init__.py",
            submodule_search_locations=[str(root)],
        )
        module = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.NODE_CLASS_MAPPINGS), 3)
        self.assertEqual(
            module.NODE_CLASS_MAPPINGS.keys(), module.NODE_DISPLAY_NAME_MAPPINGS.keys()
        )
        for node in module.NODE_CLASS_MAPPINGS.values():
            self.assertTrue(callable(getattr(node(), node.FUNCTION)))
            self.assertIn(node.CATEGORY, ("OpalFruit/YAML", "OpalFruit/Image"))


if __name__ == "__main__":
    unittest.main()
