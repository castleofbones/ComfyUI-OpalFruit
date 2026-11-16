"""Integration check against the *real* ComfyUI ``comfy_api`` host.

The CI unit suite (``python -m unittest discover -s tests -v``) runs with only
the project's declared dependencies, so the ComfyUI host is absent and the V3
node tests use the minimal stand-in in ``tests/comfyio_stub.py``. That stand-in
keeps the schema/execution/fingerprint/registration contracts meaningful, but
it is not the same code path the host runs.

This file validates the same contracts against a **genuine** ``comfy_api``: the
wrapper must be a genuine subclass of the host's ``ComfyNode`` and the output of
``execute`` must be the host's own ``NodeOutput`` class. That proves the node
works inside a real ComfyUI installation — the check the unit suite cannot do.

It is deliberately named ``comfy_integration_check.py`` so it does **not** match
the default unittest discovery pattern (``test*.py``) and is therefore excluded
from the CI run. Run it explicitly, *standalone*, with the ComfyUI root on the
path, e.g. from the project root::

    python -m unittest discover -s tests -p "comfy_integration_check*.py" -v

If the real host is not importable the suite skips; that is acceptable because
this file is outside the zero-skip CI run.
"""

from pathlib import Path
import importlib
import importlib.util
import sys
import unittest

import tempfile

from PIL import Image


def _real_host_present():
    """True only when the real on-disk ComfyUI ``comfy_api`` is importable.

    The stand-in in ``tests/comfyio_stub.py`` is a fabricated ``types.ModuleType``
    with no import spec (and ``__path__ == []``), so it is never counted as the
    host. The real host is a real on-disk package, so it always carries a spec.
    Checking the on-disk spec first means the check never treats the stand-in
    as the host, even if both were present in one process.
    """
    try:
        if importlib.util.find_spec("comfy_api") is not None:
            return True
    except (ImportError, AttributeError, ValueError):
        pass
    module = sys.modules.get("comfy_api")
    return getattr(module, "__spec__", None) is not None


_HOST = _real_host_present()


class ContactSheetIntegrationTests(unittest.TestCase):
    """V3 node schema and behaviour, exercised through the real host."""

    def setUp(self):
        if not _HOST:
            self.skipTest(
                "real ComfyUI 'comfy_api' host not importable; run this check "
                "with the ComfyUI root on sys.path to validate against the host"
            )
        from comfy_api.latest import io  # type: ignore[no-implicit-reexport]
        from nodes.image_contact_sheet import ImageContactSheet

        self.io = io
        self.node = ImageContactSheet()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_node_subclasses_real_host(self):
        """The wrapper must be a genuine subclass of the host's ComfyNode."""
        self.assertTrue(isinstance(self.node, self.io.ComfyNode))

    def test_output_node_category_function(self):
        self.assertTrue(self.node.OUTPUT_NODE)
        self.assertEqual(self.node.CATEGORY, "OpalFruit/Image")
        self.assertEqual(self.node.FUNCTION, "EXECUTE_NORMALIZED")

    def test_trigger_is_optional_any_type(self):
        trigger = next(
            i for i in self.node.GET_SCHEMA().inputs if i.id == "trigger"
        )
        self.assertEqual(trigger.io_type, "*")
        self.assertTrue(trigger.optional)

    def test_fingerprint_is_not_cached(self):
        token = self.node.fingerprint_inputs(image_directory=str(self.directory))
        self.assertNotEqual(token, token)

    def test_execute_returns_host_node_output(self):
        # A tiny source dir: two images, both valid.
        workdir = Path(self.temporary.name) / "work"
        workdir.mkdir(parents=True)
        Image.new("RGB", (20, 20), "red").save(workdir / "a.png")
        Image.new("RGBA", (30, 10), (0, 255, 0, 128)).save(workdir / "b.png")

        output = self.node.execute(
            str(workdir),
            output_filename="sheet.png",
            columns=2,
            thumbnail_width=40,
            show_labels=True,
        )

        # Must be the *host's* own NodeOutput, not the stand-in's.
        self.assertIs(type(output), self.io.NodeOutput)
        result_path = Path(output[0])
        self.assertTrue(result_path.is_absolute())
        self.assertTrue(result_path.exists())
        with Image.open(result_path) as sheet:
            self.assertEqual(sheet.mode, "RGB")
            self.assertEqual(sheet.size, (80, 64))

    def test_package_registration(self):
        # Registering the package executes the V3 contact-sheet node, which
        # imports ComfyUI's ``comfy_api``. Here the host is genuinely present,
        # so the real API is exercised.
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(
            "opalfruit_integration_package", root / "__init__.py",
            submodule_search_locations=[str(root)],
        )
        module = importlib.util.module_from_spec(spec)
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
