# ComfyUI-OpalFruit

A small, community-oriented collection of reusable ComfyUI custom nodes,
maintained by **OpalFruit**. No model-specific dependencies, GPU code, or external
controller.

| Node | Category | Inputs | Outputs |
| --- | --- | --- | --- |
| YAML Expression Loader | `OpalFruit/YAML` | `yaml_path`: YAML file path | `expressions`: list of `OPALFRUIT_EXPRESSION` dictionaries; `seed`: integer |
| YAML Expression Extractor | `OpalFruit/YAML` | `expression`: one `OPALFRUIT_EXPRESSION` dictionary | `expression`, `prompt`: strings |
| Image Contact Sheet | `OpalFruit/Image` | Directory and layout settings below | `output_path`: saved PNG path (string, not an IMAGE tensor) |

## Installation in ComfyUI Desktop

1. Use Desktop's **Open Folder → Custom Nodes** action (wording varies by
   version), or locate `custom_nodes` in your configured ComfyUI base directory.
   Do not install into Desktop's application resources.
2. Clone this repository into that directory as `ComfyUI-OpalFruit`, or extract
   its archive there with `__init__.py` directly inside the package directory.
3. In a terminal using **Desktop's Python environment**, run:
   ```sh
   python -m pip install -r /absolute/path/to/ComfyUI/custom_nodes/ComfyUI-OpalFruit/requirements.txt
   ```
4. Restart ComfyUI Desktop. Search for the display names above.

Requires Python 3.10+, PyYAML 6.0.3+, and Pillow 13.0.0+. ComfyUI itself supplies
the node host; no ComfyUI imports are needed for unit tests. Paths refer to the
machine running ComfyUI. Absolute paths are recommended; `~` is supported.

## YAML expressions and native loops

Example catalogue:

```yaml
seed: 12345
expressions:
  - expression: happy
    prompt: "A happy portrait, soft lighting"
  - expression: thoughtful
    prompt: "A thoughtful portrait, soft lighting"
```

The loader uses safe YAML parsing and requires a top-level integer seed
(booleans are rejected), a nonempty list, string `expression`/`prompt` fields,
and unique expression names. Quote values that YAML might otherwise interpret
as numbers or booleans. Missing/unreadable files and malformed data raise errors.
The loader hashes file contents for cache invalidation, even when timestamps
are unchanged.

Intended native workflow:

```text
YAML Expression Loader.expressions → Start Loop (List mode)
Start Loop current item → YAML Expression Extractor → generation/save nodes
Loop body result → End Loop (paired with Start Loop)
YAML Expression Loader.seed → generation seed input
```

The loader deliberately declares `OUTPUT_IS_LIST = (True, False)`: expressions
are a ComfyUI list output, while the seed is scalar. The extractor consumes one
dictionary, not the whole catalogue. Do not wrap the returned list in another
list or enable `INPUT_IS_LIST` on the extractor.

**Integration testing required:** no prototype implementations were present in
this repository to migrate or compare against. These are compatible scaffolds
for the stated data contract, not verified reproductions of the prototypes.
Native Start Loop/End Loop availability, socket names, custom-type acceptance,
list routing, seed propagation, and execution order must be checked in your
installed ComfyUI/Desktop version. Unit tests verify the Python contract, not
the host's loop scheduler. No loop extension or ComfyUI modification is bundled.

## Image Contact Sheet

This node works independently of YAML and generation workflows:

| Input | Default | Meaning |
| --- | --- | --- |
| `image_directory` | empty | Existing source directory |
| `filename_pattern` | `*.png` | Filename glob within that directory (not recursive) |
| `columns` | `4` | Positive number of fixed-width grid columns |
| `thumbnail_width` | `256` | Positive width and height of each image area, in pixels |
| `show_labels` | `true` | Add a 24-pixel filename label strip to each row |
| `background_colour` | `#808080` | Opaque Pillow colour name or hex colour |
| `output_filename` | `contact-sheet.png` | Plain PNG filename saved in the source directory |

Images are sorted by filename and fitted into square image areas without
distortion or upscaling. They are centred and alpha-composited over the
background; unused cells remain background-coloured. The output is RGB PNG.
Dimensions are `columns × thumbnail_width` by
`ceil(image_count / columns) × (thumbnail_width + label_height)`.
Long labels are clipped to their cells. Labels remove trailing ComfyUI counters:
`happy_00001_.png` or `happy_00001.png` becomes `happy`.

The selected output file is excluded from discovery and replaced on subsequent
runs. Other old sheets matching the glob are ordinary sources: use a dedicated
directory or narrower pattern when needed. Empty matches and unreadable images
raise clear errors rather than silently skipping files. Source images are never
edited. Output symlinks and source/output hard-link aliases are rejected.
This disk-reading output node runs again when queued, so directory changes are
not hidden by ComfyUI's cache.

Run it after image saving has finished, preferably in a separate queued
workflow. Its directory input does not establish a dependency on generation
nodes or End Loop; same-workflow ordering needs host integration testing.

## Tests

From the repository root, using an environment with the requirements installed:

```sh
python -m unittest discover -s tests -v
```

Tests use temporary files and need neither ComfyUI nor a GPU.

## Licence and attribution

Copyright 2026 OpalFruit contributors. Licensed under [Apache 2.0](LICENSE).
Maintained by OpalFruit; community contributions are welcome. ComfyUI is a
separate project; PyYAML and Pillow retain their respective licences.
