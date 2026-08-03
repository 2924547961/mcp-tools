# Visio MCP SCI

A Windows MCP server for creating fully editable Microsoft Visio diagrams with
compact SCI/IEEE styling, native arrowheads, obstacle-aware routing, and
publication-focused layout auditing.

![Layout safety preview](examples/layout-safety-preview.png)

## Design Target

The default style matches compact framework figures used in IEEE and SCI papers:
white background, thin panel borders, pastel functional fills, dark native
arrowheads, no gradients, no shadows, and readable 9-11 pt Arial text.

Connectors should look like the reference framework diagram:

- use native Visio `BeginArrow` / `EndArrow`, never triangle helper shapes;
- start routed arrows with a short segment along the side normal, then turn;
- keep ordinary neighbor connections short and clean;
- use dashed ochre arrows for decision flow;
- avoid long hook-like terminal stubs unless explicitly requested.

## Highlights

- 56 MCP tools covering documents, pages, primitives, stencils, connectors,
  alignment, export, and diagram inspection.
- Five publication palettes: `sci_compact`, `sci_nature`, `sci_ieee`,
  `sci_cell`, and `sci_mono`.
- Flat editable diamonds (`1.20 x 0.54 in` by default).
- Rounded rectangles, text boxes, polygons, arcs, Bezier curves, splines, and NURBS.
- Arial 9.5 pt body text and 10 pt multi-line text with 115% line spacing.
- Native line patterns and arrowheads; no decorative arrowhead geometry.
- Compact right-angle routing by default for nonaligned free-form connectors.
- Obstacle-aware orthogonal routing with a short 0.08 in side-normal lead-in by default.
- Optional strict terminal audit for side-normal stubs when a figure needs it.
- Strict export blocks overlap, short connectors, connector crossings, and small gaps.
- Semantic roles stored as Visio Shape Data, so validation survives save/reopen.

## Requirements

- Windows 10 or 11
- Desktop Microsoft Visio
- Python 3.10 or newer

The currently verified local runtime is Python 3.12.12.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

## MCP Configuration

Codex `config.toml`:

```toml
[mcp_servers.visio]
command = "C:\\path\\to\\visio-mcp-sci\\.venv\\Scripts\\python.exe"
args = ["-m", "visio_mcp"]
startup_timeout_sec = 120
```

Restart the MCP client after changing its configuration.

## Safe Scientific Workflow

1. Call `get_scientific_figure_standard("sci_compact")`.
2. Create shapes with `batch_draw_shapes`; assign `semantic_role` values such as
   `backbone`, `exit`, `decision`, `auxiliary`, `highlight`, `accept`, or `reject`.
3. Connect ordinary neighbors with `batch_connect_shapes`. Its defaults keep
   native arrows visible and prefer clean right-angle routing when boxes are not aligned.
4. Use `draw_safe_orthogonal_connector` only for branches that pass near other modules.
5. Call `audit_scientific_layout` and fix reported overlap/crossing/spacing issues.
6. Use `export_scientific_figure` for final SVG/PNG export.

Example obstacle-aware branch:

```json
{
  "from_shape_id": 12,
  "to_shape_id": 19,
  "obstacle_ids": [14, 15, 16],
  "preferred_axis": "horizontal",
  "clearance": 0.12,
  "terminal_stub": 0.08,
  "role": "decision_flow"
}
```

Set `terminal_stub` to `0` only when a route must be maximally compact. Use
`0.12` and `audit_terminal_geometry=true` only when you explicitly want hard
side-normal terminal checks.

## Palette Profiles

| Profile | Use |
| --- | --- |
| `sci_compact` | Default style matching the reference IDS framework figure |
| `sci_nature` | Muted blue, ochre, teal, gray, green, and vermillion |
| `sci_ieee` | Restrained blue-gray engineering palette |
| `sci_cell` | Soft categorical palette with teal emphasis |
| `sci_mono` | Monochrome print-safe palette |

## Compact SCI Defaults

| Property | Default |
| --- | ---: |
| Horizontal gap | 0.18 in |
| Vertical gap | 0.16 in |
| Minimum control/arrow gap | 0.14 in |
| Connector clearance | 0.12 in |
| Short side-normal lead-in before bend | 0.08 in |
| Rounded-corner exclusion for optional strict audit | 0.10 in |
| Flat diamond | 1.20 x 0.54 in |
| Body / multi-line text | 9.5 / 10 pt |
| Multi-line spacing | 115% |
| Data flow | charcoal solid, 1.1 pt |
| Decision flow | ochre dashed, 1.0 pt |

All shapes, polylines, and connectors remain editable native Visio objects.

## Publication-Style Basis

The defaults follow common publisher guidance: editable vector artwork, standard
fonts, minimal whitespace, restrained colors, clear line work, and no decorative
effects. Useful official references:

- [Nature research figure guide](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)
- [Science / AAAS figure instructions](https://www.science.org/content/page/instructions-authors-revised-research-articles)
- [IEEE graphics resolution and size guidance](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-graphics-for-your-article/resolution-and-size/)
- [Proceedings of the IEEE figure and table guidelines](https://proceedingsoftheieee.ieee.org/resources/guidelines-for-figures-and-tables/)
- [Elsevier artwork types and line-art guidance](https://www.elsevier.com/en-gb/about/policies-and-standards/author/artwork-and-media-instructions/artwork-types)

## Validation

Unit tests that do not launch Visio:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Windows + Visio integration smoke test:

```powershell
python tests\integration_layout_safety.py
```

## License and Attribution

MIT licensed. This repository is derived from the MIT-licensed `visio-mcp`
0.1.2 distribution by `yushun`; see [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).
