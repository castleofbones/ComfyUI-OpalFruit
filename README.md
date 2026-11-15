# ComfyUI-OpalFruit

A small, community-maintained collection of reusable **ComfyUI custom nodes** for everyday tasks. It adds a handful of ready-made boxes to ComfyUI's "Add node" menu, each doing one job, so you can build workflows without writing code.

No models, no GPU code, and no external controller are required. It works with any ComfyUI that has the native Start Loop / End Loop nodes.

**What is a custom node?** A custom node is a small Python add-in that lives in ComfyUI's `custom_nodes` folder. ComfyUI reads it on startup and shows its boxes in the UI. This directory is exactly that add-in: drop it there, install its two small dependencies, and restart ComfyUI.

## Nodes included

| Search in the UI for | What it does, in one sentence | Category |
| --- | --- | --- |
| YAML Expression Loader | Reads a YAML file of named prompts and hands each one to a loop, plus a seed | `OpalFruit/YAML` |
| YAML Expression Extractor | Takes one item from that list and splits it into the `expression` and `prompt` strings your generation nodes consume | `OpalFruit/YAML` |
| Image Contact Sheet | Stitches every image in a folder into a single labelled grid PNG, handy as a "look at all my results" page | `OpalFruit/Image` |

The two YAML nodes work together as a prompt loop. The Image Contact Sheet is completely independent — you can use it on its own or at the end of any workflow.

## Installation in ComfyUI Desktop

1. Open ComfyUI Desktop's **Custom Nodes** folder. On Desktop this is usually under *Open Folder → Custom Nodes* (wording varies by version), or the `custom_nodes` directory in your configured ComfyUI base directory. Do **not** put this into Desktop's application resources.
2. Clone this repository into that folder as `ComfyUI-OpalFruit`, or extract its archive there so that `__init__.py` sits directly inside the package directory.
3. Using a terminal that points at **Desktop's Python environment**, run:

   ```sh
   python -m pip install -r /absolute/path/to/ComfyUI/custom_nodes/ComfyUI-OpalFruit/requirements.txt
   ```

4. Restart ComfyUI Desktop and search the UI for "YAML Expression Loader", "YAML Expression Extractor", or "Image Contact Sheet".

**Requirements:** Python 3.11+, PyYAML 6.0.3+, Pillow 10.0.0+. ComfyUI itself is the host (it ships the node plumbing); you only install the two Python packages above. The Image Contact Sheet tests also need ComfyUI's own `comfy_api` on the Python path — see [Tests](#tests). Paths are relative to the machine running ComfyUI; absolute paths are recommended and `~` is supported.

## Node: YAML Expression Loader

**In plain language.** You prepare a text file listing several prompts. This box reads that file and gives you one *list* (every prompt) and one *number* (the seed). Feed the list into a ComfyUI Start Loop and the loop runs your generation/save body once per line. Wire the seed to your generation nodes so every run is reproducible.

**Example catalogue.** Save the file below as `expressions.yaml` somewhere your computer can read:

```yaml
seed: 12345
expressions:
  - expression: happy
    prompt: "A happy portrait, soft lighting"
  - expression: thoughtful
    prompt: "A thoughtful portrait, soft lighting"
```

**Intended wiring (a text view of the UI):**

```text
YAML Expression Loader.expressions --> Start Loop (List mode)
YAML Expression Loader.seed        --> generation nodes (seed input)

Start Loop current item            --> YAML Expression Extractor
YAML Expression Extractor.expression --> (label / filename / tag node)
YAML Expression Extractor.prompt   --> generation / save nodes

loop body result                   --> End Loop
```

**How it works / rules.**

- Parsing is *safe* YAML, so a catalogue file can never execute arbitrary code.
- The file must be a top-level mapping with an integer `seed` (non-negative; booleans and floats like `1.5` are rejected) and a non-empty `expressions` list.
- Every entry needs string `expression` and `prompt` fields that are non-empty and not whitespace-only.
- Expression names must be unique, compared case-insensitively (`happy`, `Happy`, `HAPPY` all collide).
- Quote values that YAML would otherwise read as numbers or booleans.
- File contents are hashed for caching, so editing the file forces a fresh read even if the file timestamp is unchanged.
- The box declares list output for `expressions` and scalar output for `seed` (`OUTPUT_IS_LIST = (True, False)`). Do **not** wrap the returned list in another list or enable `INPUT_IS_LIST` on the extractor — the list is already shaped correctly for the loop.

## Node: YAML Expression Extractor

**In plain language.** Inside the loop, this box receives *one* entry (a single dictionary) from the list and hands out two plain strings: the `expression` name and the `prompt` text. Those two strings are what the rest of your loop body connects to.

**Example wiring (one iteration of the loop):**

```text
Start Loop current item --> YAML Expression Extractor
        +-- expression --> (e.g. a filename / label node)
        +-- prompt       --> (e.g. a prompt / generation node)
```

It accepts exactly one entry of the form `{"expression": "happy", "prompt": "A happy portrait"}`, validates the same `expression`/`prompt` contract as the loader, and returns the two strings. It does **not** read the whole list.

## Node: Image Contact Sheet

**In plain language.** Point it at a folder of images (usually the ones a generation loop just saved) and it makes a single PNG: your images in neat square tiles, sorted by filename, with a small caption under each (the filename without its trailing ComfyUI counter, e.g. `happy_00001.png` shows as `happy`). Use it as a final "gallery" node so you can see everything at a glance. It is unrelated to the YAML nodes above and can be used completely on its own.

**Inputs (defaults in parentheses):**

| Input | Default | What it does |
| --- | --- | --- |
| `image_directory` | (empty) | Folder containing the source images. |
| `filename_pattern` | (`*.png`) | Filename glob selecting which files to include, in that one folder only (not recursive). |
| `columns` | (`4`) | Number of square tiles across, at least 1. |
| `thumbnail_width` | (`256`) | Width **and** height, in pixels, of each image area. |
| `show_labels` | (`true`) | Add a 24-pixel caption strip under each image. |
| `background_colour` | (`#808080`) | Opaque Pillow colour name or hex for empty cells. |
| `output_filename` | (`contact-sheet.png`) | Plain PNG filename written into `image_directory`. |
| `trigger` | (unconnected) | Optional any-type dependency hook — connect `End Loop`'s `outputs` to run the sheet after a loop. The value it carries is ignored. |

**Example 1 — a one-off sheet (no loop).**

1. Add an **Image Contact Sheet** node.
2. Set `image_directory` to the folder that holds your saved PNGs.
3. (Optional) set `filename_pattern` to `*.png` (the default) or a narrower pattern.
4. Generate. You get a single RGB PNG grid saved as `contact-sheet.png` inside that folder.

**Example 2 — a sheet after a generation loop.**

Use the `trigger` socket so the sheet runs only *after* the loop has written its images (see [Running the sheet after a loop](#running-the-sheet-after-a-loop)).

**How the sheet is laid out.**

- Images are sorted by filename and fitted into square areas **without distortion or upscaling** (large images are scaled down to fit; small images are centred, not enlarged).
- Each image is alpha-composited over the background so transparency shows correctly; cells with no image stay background-coloured.
- The output is an RGB PNG. Size is `columns × thumbnail_width` wide by `ceil(image_count / columns) × (thumbnail_width + 24)` tall when labels are on.
- Captions are centred under each image inside their own 24-pixel strip. A caption wider than its tile is pinned to the tile's left edge and clipped to the tile, so it never bleeds into a neighbour.
- Captions strip ComfyUI's trailing counter: `happy_00001_.png` or `happy_00001.png` becomes `happy`.
- The sheet file is excluded from discovery and overwritten on each run. Other older sheet files matching your glob are treated as normal source images — use a dedicated folder or a narrower pattern if that matters.
- An empty match, or an unreadable image, raises a clear error instead of silently skipping files.
- Source images are **never** modified. Output paths that are symlinks, or that hard-link back to a source, are rejected.
- Because the node always re-reads its directory, it runs again on every queued run and ComfyUI's cache does not hide directory changes.

## Running the sheet after a loop

The contact sheet only looks at its `image_directory`; that connection alone does **not** tell ComfyUI to run it after a loop. To run the sheet once a Start/End Loop has finished, connect the loop's result into the sheet's optional `trigger` socket:

```text
Start Loop --> (loop body: generate + save images) --> End Loop
                                                     |
                                                     v
                                              Image Contact Sheet.trigger
```

That link creates an execution dependency, so ComfyUI runs the sheet after the End Loop output is ready. The `trigger` carries whatever the loop returns, but the sheet **never reads it** — the sheet is driven entirely by the directory, so whatever value the loop has is irrelevant to the pixels. Left unconnected, the node behaves exactly as in the one-off example above.

> **Note on your version.** Start/End Loop and how they validate cross-loop connections are features of your installed ComfyUI/Desktop, not of this add-in. The wiring above is the intended and supported use of the socket, but if you are on an early or heavily modified build, verify in the UI that the sheet is scheduled after the loop. This package ships **no** loop extension and does **not** modify ComfyUI.

## Compatibility notes

- The nodes are complete, self-contained implementations of the data contract described above.
- They have been exercised in ComfyUI Desktop (the YAML loader driving native Start/End Loop iteration; the contact sheet generating a multi-image grid from transparent PNGs). Start/End Loop behaviour, list routing and execution ordering are properties of the ComfyUI host, not of this add-in.
- Unit tests verify the Python schema and behaviour, not the host's loop scheduler.

## Tests

Run from the repository root, in an environment with `requirements.txt` installed:

```sh
python -m unittest discover -s tests -v
```

The YAML tests are fully self-contained (no ComfyUI, no GPU). The **Image Contact Sheet** tests additionally import ComfyUI's `comfy_api` (needed by the node's schema), so run them with the ComfyUI root on the Python path (for example, from your ComfyUI installation) but still **without** a GPU. All tests use temporary files and clean up after themselves.

## Licence and attribution

Copyright 2026 OpalFruit contributors. Licensed under [Apache 2.0](LICENSE). Maintained by OpalFruit; community contributions are welcome. ComfyUI is a separate project; PyYAML and Pillow retain their respective licences.
