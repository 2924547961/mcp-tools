# Changelog

## 0.2.2

- Restored a short default side-normal lead-in before routed connectors turn.
- Kept the lead-in compact at 0.08 in to avoid the heavy hook-like look of longer stubs.
- Updated tests and documentation so the default routing matches the reference SCI framework style.

## 0.2.1

- Restored the compact reference-figure routing style: clean horizontal/vertical native connectors without visible hook-like terminal stubs by default.
- Kept perpendicular/right-angle routing as the default preference for nonaligned free-form connectors.
- Made terminal stub checks optional through `audit_terminal_geometry`.
- Added publication palette profiles: `sci_nature`, `sci_ieee`, `sci_cell`, and `sci_mono`.
- Updated documentation to emphasize editable vector artwork, restrained palettes, native arrows, and compact SCI/IEEE layout.

## 0.2.0

- Added compact SCI/IEEE palette, typography, spacing, and semantic roles.
- Added native line pattern, arrowhead, cap, rounding, and routing controls.
- Added rounded rectangles, text boxes, flat diamonds, polygons, arcs, and curves.
- Added exact compact layout, alignment, distribution, duplication, and z-order tools.
- Added automatic minimum clearance before free-form AutoConnect.
- Added obstacle-aware orthogonal routing.
- Added geometry audit and strict audit-gated scientific export.
- Added multi-line 115% spacing and paragraph spacing controls.
