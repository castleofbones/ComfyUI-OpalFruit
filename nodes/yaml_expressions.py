"""Load YAML expression catalogues and extract individual loop entries."""

import hashlib
from pathlib import Path

import yaml


EXPRESSION_TYPE = "OPALFRUIT_EXPRESSION"


def validate_expression(value):
    if not isinstance(value, dict):
        raise ValueError("Each expression must be a dictionary.")
    for field in ("expression", "prompt"):
        if field not in value or not isinstance(value[field], str):
            raise ValueError(f"Each expression requires a string '{field}' field.")
        if not value[field].strip():
            raise ValueError(f"Each expression's '{field}' must be nonempty and not whitespace.")
    return value


class YAMLExpressionLoader:
    CATEGORY = "OpalFruit/YAML"
    FUNCTION = "load"
    RETURN_TYPES = (EXPRESSION_TYPE, "INT")
    RETURN_NAMES = ("expressions", "seed")
    OUTPUT_IS_LIST = (True, False)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"yaml_path": ("STRING", {"default": ""})}}

    @classmethod
    def IS_CHANGED(cls, yaml_path):
        try:
            return hashlib.sha256(Path(yaml_path).expanduser().read_bytes()).hexdigest()
        except OSError:
            return float("nan")

    def load(self, yaml_path):
        path = Path(yaml_path).expanduser()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"Cannot read YAML catalogue '{path}': {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("YAML catalogue must be a top-level dictionary.")
        seed = data.get("seed")
        if type(seed) is not int:
            raise ValueError("YAML catalogue requires an integer 'seed'.")
        if seed < 0:
            raise ValueError("YAML catalogue 'seed' must not be negative.")
        expressions = data.get("expressions")
        if not isinstance(expressions, list) or not expressions:
            raise ValueError("YAML catalogue requires a nonempty 'expressions' list.")
        seen = set()
        for value in expressions:
            entry = validate_expression(value)
            name = entry["expression"]
            key = name.casefold()
            if key in seen:
                raise ValueError(f"Duplicate expression name: {name!r}.")
            seen.add(key)
        return expressions, seed


class YAMLExpressionExtractor:
    CATEGORY = "OpalFruit/YAML"
    FUNCTION = "extract"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("expression", "prompt")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"expression": (EXPRESSION_TYPE,)}}

    def extract(self, expression):
        entry = validate_expression(expression)
        return entry["expression"], entry["prompt"]
