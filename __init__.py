"""ComfyUI registration for the OpalFruit node collection."""

from .nodes.yaml_expressions import YAMLExpressionLoader, YAMLExpressionExtractor
from .nodes.image_contact_sheet import ImageContactSheet


NODE_CLASS_MAPPINGS = {
    "OpalFruitYAMLExpressionLoader": YAMLExpressionLoader,
    "OpalFruitYAMLExpressionExtractor": YAMLExpressionExtractor,
    "OpalFruitImageContactSheet": ImageContactSheet,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OpalFruitYAMLExpressionLoader": "YAML Expression Loader",
    "OpalFruitYAMLExpressionExtractor": "YAML Expression Extractor",
    "OpalFruitImageContactSheet": "Image Contact Sheet",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
