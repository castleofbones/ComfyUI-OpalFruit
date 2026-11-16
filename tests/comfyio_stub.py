"""Minimal in-memory stand-in for ComfyUI's ``comfy_api``.

The V3 node tests must run under CI (Python 3.13) with **only** the project's
declared dependencies installed — i.e. with no ComfyUI host and therefore no
``comfy_api`` on the path. This module fabricates just enough of
``comfy_api.latest.io`` to drive the V3 node wrapper (``ImageContactSheet``)
and to keep its schema, execution, fingerprint and registration contracts
meaningful:

- ``Schema.validate`` rejects duplicate input/output ids, exactly as the host.
- ``ComfyNode`` validates the ``define_schema`` / ``execute`` contract.
- ``FUNCTION`` / ``CATEGORY`` / ``OUTPUT_NODE`` / ``DESCRIPTION`` expose the
  schema-derived values through a ``classproperty`` (as the host does).

If a real ``comfy_api`` is already importable (the ComfyUI host on the Python
path), the real one is used and nothing is fabricated.

This file is test-only infrastructure. It is not a dependency of the package.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import types


def comfy_api_available() -> bool:
    """True when a usable ``comfy_api`` is present.

    This is True when ``comfy_api`` is already a module in the current process
    (either the real host, or a stand-in previously installed by this module) or
    when the import machinery can locate a real ``comfy_api`` on the path.
    Checking ``sys.modules`` first avoids re-fabricating the stand-in when it is
    the module already in use, and avoids ``find_spec``'s ``sys.modules``
    interaction.
    """
    if "comfy_api" in sys.modules:
        return True
    return importlib.util.find_spec("comfy_api") is not None


def install_if_missing() -> None:
    """Install a minimal ``comfy_api`` stand-in only when no usable one is present.

    Idempotent: if the real host is on the path (or already imported in this
    process) or a stand-in was already installed, nothing happens and the
    existing ``comfy_api`` is used.
    """
    if comfy_api_available():
        return
    _install()


# ---------------------------------------------------------------------------
# Stand-in classes. Defined at module level so mutual references resolve; they
# are only injected into a fabricated ``comfy_api`` when the host is absent.
# ---------------------------------------------------------------------------

class classproperty:
    """Descriptor exposing a class-level accessor on both the class and instances.

    Mirrors ``comfy_api.internal.classproperty`` closely enough for node
    attributes like ``CATEGORY`` / ``OUTPUT_NODE`` / ``FUNCTION``.
    """

    def __init__(self, func):
        self.func = func
        self.__name__ = getattr(func, "__name__", "classproperty")
        self.__qualname__ = getattr(func, "__qualname__", self.__name__)

    def __get__(self, obj, owner=None):
        if isinstance(obj, type):
            cls = obj
        elif obj is not None:
            cls = type(obj)
        else:
            cls = owner
        return self.func(cls)

    def __set__(self, obj, value):
        raise AttributeError("read-only descriptor")


class _ComfyInputBase:
    """Shared base for the stand-in V3 Input classes."""

    io_type = ""

    def __init__(
        self,
        id,
        display_name=None,
        optional=False,
        tooltip=None,
        default=None,
        min=None,
        max=None,
    ):
        if not isinstance(id, str) or not id:
            raise ValueError(f"Input id required, got {id!r}.")
        self.id = id
        self.display_name = display_name
        self.optional = optional
        self.tooltip = tooltip
        self.default = default
        self.min = min
        self.max = max

    def get_all(self):
        return [self]

    def validate(self):
        pass

    def as_dict(self):
        return {
            "id": self.id,
            "io_type": self.io_type,
            "display_name": self.display_name,
            "optional": self.optional,
            "tooltip": self.tooltip,
            "default": self.default,
            "min": self.min,
            "max": self.max,
        }


class _ComfyOutputBase:
    """Shared base for the stand-in V3 Output classes."""

    io_type = ""

    def __init__(self, id=None, display_name=None, tooltip=None):
        self.id = id
        self.display_name = display_name
        self.tooltip = tooltip

    def validate(self):
        pass

    def as_dict(self):
        return {
            "io_type": self.io_type,
            "display_name": self.display_name,
            "tooltip": self.tooltip,
        }


class String:
    io_type = "STRING"

    class Input(_ComfyInputBase):
        io_type = "STRING"

    class Output(_ComfyOutputBase):
        io_type = "STRING"


class Int:
    io_type = "INT"

    class Input(_ComfyInputBase):
        io_type = "INT"


class Boolean:
    io_type = "BOOLEAN"

    class Input(_ComfyInputBase):
        io_type = "BOOLEAN"


class AnyType:
    """Match-all socket type, as used by native Start/End Loop output sockets."""

    io_type = "*"

    class Input(_ComfyInputBase):
        io_type = "*"

    class Output(_ComfyOutputBase):
        io_type = "*"


class Schema:
    """Definition of a V3 node, mirroring the host's schema contract."""

    def __init__(
        self,
        node_id,
        display_name=None,
        category="sd",
        description="",
        inputs=None,
        outputs=None,
        is_output_node=False,
        is_input_list=False,
        is_experimental=False,
        is_deprecated=False,
        is_dev_only=False,
        is_api_node=False,
        not_idempotent=False,
    ):
        self.node_id = node_id
        self.display_name = display_name
        self.category = category
        self.description = description
        self.inputs = list(inputs) if inputs is not None else []
        self.outputs = list(outputs) if outputs is not None else []
        self.hidden = []
        self.is_output_node = is_output_node
        self.is_input_list = is_input_list
        self.is_experimental = is_experimental
        self.is_deprecated = is_deprecated
        self.is_dev_only = is_dev_only
        self.is_api_node = is_api_node
        self.not_idempotent = not_idempotent
        self.enable_expand = False

    def finalize(self):
        # Give outputs without ids a stable default id (mirrors the host).
        for index, output in enumerate(self.outputs):
            if output.id is None:
                output.id = f"_{index}_{output.io_type}_"
        return self

    def validate(self):
        """Reject duplicate input ids and output ids, as the host does."""
        nested_inputs = []
        for input in self.inputs:
            nested_inputs.extend(input.get_all())
        input_ids = [i.id for i in nested_inputs]
        output_ids = [o.id for o in self.outputs]
        issues = []
        if len(set(input_ids)) != len(input_ids):
            duplicates = [i for i in set(input_ids) if input_ids.count(i) > 1]
            issues.append(
                f"Input ids must be unique, but {duplicates} are not."
            )
        if len(set(output_ids)) != len(output_ids):
            duplicates = [i for i in set(output_ids) if output_ids.count(i) > 1]
            issues.append(
                f"Output ids must be unique, but {duplicates} are not."
            )
        if issues:
            raise ValueError("\n".join(issues))
        for input in self.inputs:
            input.validate()
        for output in self.outputs:
            output.validate()
        return self


class NodeOutput:
    """Standardized output of a node, mirroring the host's ``NodeOutput``."""

    def __init__(self, *args, ui=None, expand=None, block_execution=None):
        self.args = args
        self.ui = ui
        self.expand = expand
        self.block_execution = block_execution

    @property
    def result(self):
        return self.args if len(self.args) > 0 else None

    @classmethod
    def from_dict(cls, data):
        args = ()
        ui = None
        expand = None
        if "result" in data:
            result = data["result"]
            if isinstance(result, tuple):
                args = result
        if "ui" in data:
            ui = data["ui"]
        if "expand" in data:
            expand = data["expand"]
        return cls(*args, ui=ui, expand=expand)

    def __getitem__(self, index):
        return self.args[index]


def _override_owner(cls, name):
    """First class in the MRO that defines ``name`` in its own ``__dict__``."""
    for base in cls.__mro__:
        if name in base.__dict__:
            return base
    return None


def _is_async(func):
    """True when a node ``execute`` is an async coroutine function."""
    func_obj = getattr(func, "__func__", None) or func
    return inspect.iscoroutinefunction(func_obj)


class ComfyNode:
    """Common base class for all V3 nodes, mirroring the host contract."""

    _DESCRIPTION = None
    _CATEGORY = None
    _OUTPUT_NODE = None
    SCHEMA = None

    def __init__(self):
        self.VALIDATE_CLASS()

    @classmethod
    def define_schema(cls):
        """Override to return a ``Schema``. The base raises."""
        raise NotImplementedError

    @classmethod
    def execute(cls, **kwargs):
        """Override to perform the node's work. The base raises."""
        raise NotImplementedError

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        """Optional input fingerprint (host default: no change)."""
        raise NotImplementedError

    @classmethod
    def check_lazy_status(cls, **kwargs):
        return [name for name in kwargs if kwargs[name] is None]

    @classmethod
    def VALIDATE_CLASS(cls):
        for name in ("define_schema", "execute"):
            if _override_owner(cls, name) is ComfyNode:
                raise Exception(
                    f"No {name} function was defined for node class "
                    f"{cls.__name__}."
                )

    @classmethod
    def FINALIZE_SCHEMA(cls):
        schema = cls.define_schema()
        schema.finalize()
        return schema

    @classmethod
    def GET_SCHEMA(cls):
        cls.VALIDATE_CLASS()
        schema = cls.FINALIZE_SCHEMA()
        schema.validate()
        if cls._DESCRIPTION is None:
            cls._DESCRIPTION = schema.description
        if cls._CATEGORY is None:
            cls._CATEGORY = schema.category
        if cls._OUTPUT_NODE is None:
            cls._OUTPUT_NODE = schema.is_output_node
        cls.SCHEMA = schema
        return schema

    @classmethod
    def EXECUTE_NORMALIZED(cls, *args, **kwargs):
        to_return = cls.execute(*args, **kwargs)
        if to_return is None:
            to_return = NodeOutput()
        elif isinstance(to_return, NodeOutput):
            pass
        elif isinstance(to_return, tuple):
            to_return = NodeOutput(*to_return)
        elif isinstance(to_return, dict):
            to_return = NodeOutput.from_dict(to_return)
        else:
            raise Exception(f"Invalid return type from node: {type(to_return)}")
        if to_return.expand is not None and not cls.SCHEMA.enable_expand:
            raise Exception(
                f"Node {cls.__name__} is not expandable, but expand is included "
                "in NodeOutput."
            )
        return to_return

    @classmethod
    def GET_BASE_CLASS(cls):
        return ComfyNode

    @classproperty
    def FUNCTION(cls):
        return (
            "EXECUTE_NORMALIZED_ASYNC"
            if _is_async(cls.execute)
            else "EXECUTE_NORMALIZED"
        )

    @classproperty
    def DESCRIPTION(cls):
        if cls._DESCRIPTION is None:
            cls.GET_SCHEMA()
        return cls._DESCRIPTION

    @classproperty
    def CATEGORY(cls):
        if cls._CATEGORY is None:
            cls.GET_SCHEMA()
        return cls._CATEGORY

    @classproperty
    def OUTPUT_NODE(cls):
        if cls._OUTPUT_NODE is None:
            cls.GET_SCHEMA()
        return cls._OUTPUT_NODE


def _install():
    """Wire the stand-in classes into a fabricated ``comfy_api`` package."""
    io_mod = types.ModuleType("comfy_api.latest.io")
    io_mod.__package__ = "comfy_api.latest"
    io_mod.__dict__.update(
        {
            "ComfyNode": ComfyNode,
            "Schema": Schema,
            "NodeOutput": NodeOutput,
            "String": String,
            "Int": Int,
            "Boolean": Boolean,
            "AnyType": AnyType,
            "classproperty": classproperty,
        }
    )

    latest_mod = types.ModuleType("comfy_api.latest")
    latest_mod.io = io_mod
    latest_mod.__package__ = "comfy_api"
    latest_mod.__path__ = []

    pkg_mod = types.ModuleType("comfy_api")
    pkg_mod.latest = latest_mod
    pkg_mod.__package__ = ""
    pkg_mod.__path__ = []

    for name, mod in (
        ("comfy_api", pkg_mod),
        ("comfy_api.latest", latest_mod),
        ("comfy_api.latest.io", io_mod),
    ):
        sys.modules[name] = mod
