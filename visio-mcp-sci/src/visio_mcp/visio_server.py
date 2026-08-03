"""Visio MCP Server — exposes Visio COM automation as MCP tools."""

import sys
import json
import logging
import traceback

from mcp.server.fastmcp import FastMCP

from visio_mcp.visio_app import VisioApp, get_scientific_style_profile
from visio_mcp.diagram_standards import STANDARDS, list_types, get_standard

# Logging to stderr (stdout is reserved for MCP stdio transport)
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP("visio")
visio = VisioApp()


def _ok(result) -> str:
    """Serialize result to JSON string."""
    return json.dumps(result, ensure_ascii=False, indent=2)


def _err(e: Exception) -> str:
    """Format error for tool response."""
    tb = traceback.format_exc()
    logger.error(tb)
    return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
def get_scientific_figure_standard(profile: str = "sci_compact") -> str:
    """Get the required compact scientific-figure drawing standard.

    Call this before free-form academic diagrams. The returned profile defines a
    print-friendly SCI/IEEE palette, typography, exact compact gaps, short nodes,
    flat diamond proportions, and native solid/dashed arrow styling.

    Default rules include 0.16 in vertical gaps, 0.18 in horizontal gaps,
    1.20 x 0.54 in flat diamonds, Arial 9.5 pt body text, slightly larger 10 pt
    multi-line text, and 115% line spacing. Explicit user formatting may override it.
    """
    try:
        return _ok(get_scientific_style_profile(profile))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Document Management
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def create_document(template: str = "") -> str:
    """Create a new blank Visio document.

    WARNING: Do NOT use this for standard diagram types (flowchart, UML, BPMN, ERD,
    network, etc.). Use create_diagram(diagram_type) instead — it loads the correct
    template with pre-configured stencils and page settings.

    Only use create_document() for free-form drawings that don't match any standard type.

    Args:
        template: Optional template file path or name. Empty for blank document.
    """
    try:
        return _ok(visio.create_document(template))
    except Exception as e:
        return _err(e)


@mcp.tool()
def open_document(file_path: str) -> str:
    """Open an existing Visio file (.vsdx, .vsd, etc.).

    Args:
        file_path: Full path to the Visio file.
    """
    try:
        return _ok(visio.open_document(file_path))
    except Exception as e:
        return _err(e)


@mcp.tool()
def save_document(doc_name: str = "") -> str:
    """Save a document.

    Args:
        doc_name: Document name. Empty for active document.
    """
    try:
        return _ok(visio.save_document(doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def save_document_as(file_path: str, doc_name: str = "") -> str:
    """Save the document to a new path.

    Args:
        file_path: Target file path (e.g. 'C:/output/diagram.vsdx').
        doc_name: Document name. Empty for active document.
    """
    try:
        return _ok(visio.save_document_as(file_path, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def close_document(doc_name: str = "") -> str:
    """Close a document.

    Args:
        doc_name: Document name. Empty for active document.
    """
    try:
        return _ok(visio.close_document(doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_open_documents() -> str:
    """List all open Visio documents (excluding stencils)."""
    try:
        return _ok(visio.list_open_documents())
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Page Operations
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def list_pages(doc_name: str = "") -> str:
    """List all pages in a document.

    Args:
        doc_name: Document name. Empty for active document.
    """
    try:
        return _ok(visio.list_pages(doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def add_page(page_name: str = "", doc_name: str = "") -> str:
    """Add a new page to the document.

    Args:
        page_name: Name for the new page. Empty for default name.
        doc_name: Document name. Empty for active document.
    """
    try:
        return _ok(visio.add_page(page_name, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_page_size(
    width: float, height: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Set the Visio page size in inches for paper-ready aspect ratios."""
    try:
        return _ok(visio.set_page_size(width, height, _parse_page(page), doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_active_page(page: str, doc_name: str = "") -> str:
    """Set the active page by name or 1-based index.

    Args:
        page: Page name (string) or 1-based index (number as string, e.g. '2').
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref: str | int = page
        try:
            page_ref = int(page)
        except ValueError:
            pass
        return _ok(visio.set_active_page(page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_page(page: str, doc_name: str = "") -> str:
    """Delete a page by name or 1-based index.

    Args:
        page: Page name or 1-based index (as string).
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref: str | int = page
        try:
            page_ref = int(page)
        except ValueError:
            pass
        return _ok(visio.delete_page(page_ref, doc_name))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Shape Operations
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def drop_shape(
    master_name: str,
    stencil_name: str,
    x: float,
    y: float,
    text: str = "",
    fill_color: str = "",
    line_color: str = "",
    line_weight: str = "",
    font_size: str = "",
    font_color: str = "",
    transparency: str = "",
    page: str = "",
    doc_name: str = "",
) -> str:
    """Drop a master shape from a stencil onto the page.

    IMPORTANT: For standard diagram types, use the master names and stencils specified
    by get_diagram_standard(). Do NOT guess master names — incorrect names will cause errors.
    Prefer batch_draw_shapes() for creating multiple shapes at once.

    Args:
        master_name: Name of the master shape in the stencil (e.g. 'Process', 'Decision').
        stencil_name: Stencil file name (e.g. 'BASIC_M.vssx') or full path.
        x: X position in inches from bottom-left.
        y: Y position in inches from bottom-left.
        text: Optional text to set on the shape.
        fill_color: Optional fill color formula, e.g. 'RGB(255,0,0)'.
        line_color: Optional line/border color formula.
        line_weight: Optional line weight, e.g. '2 pt'.
        font_size: Optional font size, e.g. '14 pt'.
        font_color: Optional font color formula.
        transparency: Optional fill transparency, e.g. '50%'.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        result = visio.drop_shape(master_name, stencil_name, x, y, page_ref, doc_name)
        shape_id = result["shape_id"]
        if text:
            visio.set_shape_text(shape_id, text, page_ref, doc_name)
            result["text"] = text
        if any([fill_color, line_color, line_weight, font_size, font_color, transparency]):
            visio.set_shape_format(
                shape_id, fill_color, line_color, line_weight,
                font_size, font_color, transparency, page_ref, doc_name,
            )
        return _ok(result)
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_rectangle(
    x1: float, y1: float, x2: float, y2: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a rectangle. Coordinates in inches: (x1,y1)=bottom-left, (x2,y2)=top-right.

    NOTE: For standard diagram types, do NOT use raw rectangles as substitutes for stencil
    shapes. Use drop_shape() or batch_draw_shapes() with the correct master from the standard.

    Args:
        x1: Left edge X in inches.
        y1: Bottom edge Y in inches.
        x2: Right edge X in inches.
        y2: Top edge Y in inches.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.draw_rectangle(x1, y1, x2, y2, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_oval(
    x1: float, y1: float, x2: float, y2: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw an oval/ellipse within the bounding box. Coordinates in inches.

    NOTE: For standard diagram types, do NOT use raw ovals as substitutes for stencil
    shapes. Use drop_shape() or batch_draw_shapes() with the correct master from the standard.

    Args:
        x1: Left edge X in inches.
        y1: Bottom edge Y in inches.
        x2: Right edge X in inches.
        y2: Top edge Y in inches.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.draw_oval(x1, y1, x2, y2, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_line(
    x1: float, y1: float, x2: float, y2: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a line from (x1,y1) to (x2,y2). Coordinates in inches.

    Args:
        x1: Start X in inches.
        y1: Start Y in inches.
        x2: End X in inches.
        y2: End Y in inches.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.draw_line(x1, y1, x2, y2, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_polyline(
    points: str,
    flags: int = 0,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a polyline (multi-segment line or closed polygon). Coordinates in inches.

    Args:
        points: JSON array of coordinates [x1,y1, x2,y2, ...].
                To close the polygon, repeat the first point at the end.
        flags: 0 = open polyline (default), 1 = fill shape.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        pts = json.loads(points)
        page_ref = _parse_page(page)
        return _ok(visio.draw_polyline(pts, flags, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_bezier(
    points: str,
    degree: int = 3,
    flags: int = 0,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a Bezier curve. Coordinates in inches.

    Args:
        points: JSON array of control points [x1,y1, x2,y2, ...].
                For cubic (degree 3): need 3n+1 point pairs (start + groups of 3).
        degree: 1 (linear), 2 (quadratic), or 3 (cubic, default).
        flags: 0 = default.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        pts = json.loads(points)
        page_ref = _parse_page(page)
        return _ok(visio.draw_bezier(pts, degree, flags, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_quarter_arc(
    x1: float, y1: float, x2: float, y2: float,
    sweep: int = 0,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a quarter-arc from (x1,y1) to (x2,y2). Coordinates in inches.

    Args:
        x1: Start X in inches.
        y1: Start Y in inches.
        x2: End X in inches.
        y2: End Y in inches.
        sweep: 0 = convex (default), 1 = concave.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.draw_quarter_arc(x1, y1, x2, y2, sweep, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_arc_by_three_points(
    x1: float, y1: float, x2: float, y2: float,
    control_x: float, control_y: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a native editable Visio arc through begin, end, and control points."""
    try:
        return _ok(visio.draw_arc_by_three_points(
            x1, y1, x2, y2, control_x, control_y,
            _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_regular_polygon(
    center_x: float, center_y: float, radius: float, sides: int,
    rotation: float = 0.0,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a native editable regular polygon with 3 or more sides."""
    try:
        return _ok(visio.draw_regular_polygon(
            center_x, center_y, radius, sides, rotation,
            _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_compact_diamond(
    center_x: float, center_y: float,
    width: float = 1.20, height: float = 0.54,
    text: str = "", role: str = "decision", profile: str = "sci_compact",
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a flat native Visio diamond for compact scientific decision nodes.

    The default 1.20:0.54 proportion is intentionally flatter than a rotated square.
    It remains a normal editable Visio geometry, not a raster image or icon.
    """
    try:
        page_ref = _parse_page(page)
        result = visio.draw_diamond(
            center_x, center_y, width, height, _parse_page(page), doc_name,
        )
        shape_id = int(result["shape_id"])
        if text:
            visio.set_shape_text(shape_id, text, page_ref, doc_name)
        return _ok(visio.apply_scientific_style(
            shape_id, role, profile, page_ref, doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_spline(
    points: str,
    tolerance: float = 0.25,
    flags: int = 0,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a smooth spline through a set of points. Coordinates in inches.

    Args:
        points: JSON array of coordinates [x1,y1, x2,y2, ...].
        tolerance: How closely the spline follows the points (inches). Default 0.25.
        flags: 0 = default.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        pts = json.loads(points)
        page_ref = _parse_page(page)
        return _ok(visio.draw_spline(pts, tolerance, flags, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_nurbs(
    degree: int,
    control_points: str,
    knots: str,
    weights: str = "",
    page: str = "", doc_name: str = "",
) -> str:
    """Draw a NURBS (Non-Uniform Rational B-Spline) curve.

    Args:
        degree: Degree of the curve (e.g. 3 for cubic).
        control_points: JSON array of control points [x1,y1, x2,y2, ...] in inches.
        knots: JSON array of knot values. Length = num_control_points + degree + 1.
        weights: JSON array of weights per control point. Empty for uniform (all 1.0).
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        cp = json.loads(control_points)
        k = json.loads(knots)
        w = json.loads(weights) if weights else None
        page_ref = _parse_page(page)
        return _ok(visio.draw_nurbs(degree, cp, k, w, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def connect_shapes(
    from_shape_id: int,
    to_shape_id: int,
    connector_master: str = "",
    connector_stencil: str = "",
    from_port: int = -1,
    to_port: int = -1,
    line_color: str = "",
    line_weight: str = "",
    line_pattern: str = "",
    begin_arrow: str = "",
    end_arrow: str = "",
    begin_arrow_size: str = "",
    end_arrow_size: str = "",
    line_transparency: str = "",
    line_cap: str = "",
    rounding: str = "",
    route_style: str = "",
    connector_appearance: str = "",
    page: str = "",
    doc_name: str = "",
) -> str:
    """Connect two shapes with a connector line.

    IMPORTANT: For standard diagram types (UML, BPMN, ERD, etc.), you MUST use the
    connector_master and connector_stencil specified by get_diagram_standard().
    Using AutoConnect (empty connector_master) produces generic arrows that lack
    correct semantics (e.g. UML inheritance needs hollow triangle arrowheads).

    Args:
        from_shape_id: Source shape ID (returned by shape creation tools).
        to_shape_id: Target shape ID.
        connector_master: Connector master name. Empty uses AutoConnect (only for free-form diagrams).
        connector_stencil: Stencil for custom connector.
        from_port: Connection point row index on source shape. -1 uses PinX (default).
                   For sequence diagrams, use this to attach messages to specific
                   points along the lifeline (0 = top of lifeline, increasing downward).
        to_port: Connection point row index on target shape. -1 uses PinX (default).
        line_pattern: "solid", "dashed", or a native Visio pattern index/formula.
        begin_arrow/end_arrow: Native line arrowhead style 0-45; "standard" maps to 4.
        begin_arrow_size/end_arrow_size: Native Visio arrow-size values.
        route_style: "right_angle", "straight", "simple_hv", "simple_vh", etc.
        connector_appearance: "default", "straight", or "curved".
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.connect_shapes(
            from_shape_id, to_shape_id,
            connector_master, connector_stencil,
            from_port, to_port, page_ref, doc_name,
            line_color=line_color, line_weight=line_weight,
            line_pattern=line_pattern, begin_arrow=begin_arrow,
            end_arrow=end_arrow, begin_arrow_size=begin_arrow_size,
            end_arrow_size=end_arrow_size, line_transparency=line_transparency,
            line_cap=line_cap, rounding=rounding, route_style=route_style,
            connector_appearance=connector_appearance,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_shape_text(
    shape_id: int, text: str,
    page: str = "", doc_name: str = "",
) -> str:
    """Set the text content of a shape.

    Args:
        shape_id: Shape ID.
        text: Text to set on the shape.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.set_shape_text(shape_id, text, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_shape_format(
    shape_id: int,
    fill_color: str = "",
    line_color: str = "",
    line_weight: str = "",
    font_size: str = "",
    font_color: str = "",
    transparency: str = "",
    line_pattern: str = "",
    begin_arrow: str = "",
    end_arrow: str = "",
    begin_arrow_size: str = "",
    end_arrow_size: str = "",
    line_transparency: str = "",
    line_cap: str = "",
    rounding: str = "",
    route_style: str = "",
    connector_appearance: str = "",
    fill_background_color: str = "",
    fill_pattern: str = "",
    fill_background_transparency: str = "",
    font_name: str = "",
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    h_align: str = "",
    v_align: str = "",
    text_margin_left: str = "",
    text_margin_right: str = "",
    text_margin_top: str = "",
    text_margin_bottom: str = "",
    text_background_color: str = "",
    text_background_transparency: str = "",
    line_spacing: str = "",
    paragraph_before: str = "",
    paragraph_after: str = "",
    angle: str = "",
    page: str = "",
    doc_name: str = "",
) -> str:
    """Set visual formatting of a shape.

    Color values use Visio formulas: 'RGB(255,0,0)' for red, 'RGB(0,0,255)' for blue.
    This is the unified quick-edit tool for native Visio shapes and connectors.
    It supports fill, line pattern, line-native arrowheads, text, rotation,
    alignment, margins, and connector routing.

    Args:
        shape_id: Shape ID.
        fill_color: Fill color formula, e.g. 'RGB(255,0,0)'.
        line_color: Line/border color formula.
        line_weight: Line weight, e.g. '2 pt'.
        font_size: Font size, e.g. '14 pt'.
        font_color: Font color formula.
        transparency: Fill transparency, e.g. '50%'.
        line_pattern: "solid", "dashed", or native Visio index/formula.
        begin_arrow/end_arrow: Native arrowhead style 0-45; no polygon helper is needed.
        font_name: Font family, e.g. "Arial" or "Times New Roman".
        bold/italic/underline: Toggle whole-shape text styling.
        h_align: left, center, right, justify, force_justify.
        v_align: top, middle, bottom.
        line_spacing: Multi-line spacing, normally "115%" for compact SCI figures.
        paragraph_before/paragraph_after: Small paragraph gaps, e.g. "0.5 pt".
        angle: Shape rotation, e.g. "30 deg" or numeric degrees.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.set_shape_format(
            shape_id, fill_color, line_color, line_weight,
            font_size, font_color, transparency, page_ref, doc_name,
            line_pattern=line_pattern, begin_arrow=begin_arrow,
            end_arrow=end_arrow, begin_arrow_size=begin_arrow_size,
            end_arrow_size=end_arrow_size, line_transparency=line_transparency,
            line_cap=line_cap, rounding=rounding, route_style=route_style,
            connector_appearance=connector_appearance,
            fill_background_color=fill_background_color, fill_pattern=fill_pattern,
            fill_background_transparency=fill_background_transparency,
            font_name=font_name, bold=bold, italic=italic, underline=underline,
            h_align=h_align, v_align=v_align,
            text_margin_left=text_margin_left, text_margin_right=text_margin_right,
            text_margin_top=text_margin_top, text_margin_bottom=text_margin_bottom,
            text_background_color=text_background_color,
            text_background_transparency=text_background_transparency,
            line_spacing=line_spacing, paragraph_before=paragraph_before,
            paragraph_after=paragraph_after,
            angle=angle,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_connector_format(
    shape_id: int,
    line_color: str = "",
    line_weight: str = "",
    line_pattern: str = "",
    begin_arrow: str = "",
    end_arrow: str = "",
    begin_arrow_size: str = "",
    end_arrow_size: str = "",
    line_transparency: str = "",
    line_cap: str = "",
    rounding: str = "",
    route_style: str = "",
    connector_appearance: str = "",
    page: str = "", doc_name: str = "",
) -> str:
    """Quickly format a connector using native Visio line properties.

    Use end_arrow="standard" for a normal line-native arrowhead and
    line_pattern="dashed" for a native dashed line. Do not add triangle shapes.
    Arrowhead styles can also be specified as Visio indices 0-45.
    """
    try:
        return _ok(visio.set_shape_format(
            shape_id, page_name_or_index=_parse_page(page), doc_name=doc_name,
            line_color=line_color, line_weight=line_weight,
            line_pattern=line_pattern, begin_arrow=begin_arrow,
            end_arrow=end_arrow, begin_arrow_size=begin_arrow_size,
            end_arrow_size=end_arrow_size, line_transparency=line_transparency,
            line_cap=line_cap, rounding=rounding, route_style=route_style,
            connector_appearance=connector_appearance,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def move_shape(
    shape_id: int, x: float, y: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Move a shape to a new position.

    Args:
        shape_id: Shape ID.
        x: New X position in inches.
        y: New Y position in inches.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.move_shape(shape_id, x, y, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def resize_shape(
    shape_id: int, width: float, height: float,
    page: str = "", doc_name: str = "",
) -> str:
    """Resize a shape.

    Args:
        shape_id: Shape ID.
        width: New width in inches.
        height: New height in inches.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.resize_shape(shape_id, width, height, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def duplicate_shape(
    shape_id: int, offset_x: float = 0.25, offset_y: float = -0.25,
    page: str = "", doc_name: str = "",
) -> str:
    """Duplicate a native Visio shape and offset the editable copy."""
    try:
        return _ok(visio.duplicate_shape(
            shape_id, offset_x, offset_y, _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def set_z_order(
    shape_id: int, action: str,
    page: str = "", doc_name: str = "",
) -> str:
    """Change z-order: bring_to_front, send_to_back, bring_forward, send_backward."""
    try:
        return _ok(visio.set_z_order(shape_id, action, _parse_page(page), doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def align_shapes(
    shape_ids: list[int], alignment: str, reference_shape_id: int = 0,
    page: str = "", doc_name: str = "",
) -> str:
    """Align editable shapes: left, center, right, top, middle, or bottom."""
    try:
        return _ok(visio.align_shapes(
            shape_ids, alignment, reference_shape_id, _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def distribute_shapes(
    shape_ids: list[int], distribution: str,
    page: str = "", doc_name: str = "",
) -> str:
    """Distribute shapes using horizontal/vertical center or equal spacing.

    distribution: horizontal_center, horizontal_space,
    vertical_middle, or vertical_space.
    """
    try:
        return _ok(visio.distribute_shapes(
            shape_ids, distribution, _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def compact_layout_shapes(
    shape_ids: list[int], axis: str = "vertical", gap: float = 0.16,
    order: str = "auto", preserve_center: bool = True,
    page: str = "", doc_name: str = "",
) -> str:
    """Pack editable controls using a small exact edge-to-edge gap.

    Use 0.16 in vertically and 0.18 in horizontally for the default compact SCI
    layout. Auto order is top-to-bottom vertically and left-to-right horizontally.
    Connectors are excluded; compact controls first, then connect them.
    """
    try:
        return _ok(visio.compact_layout_shapes(
            shape_ids, axis, gap, order, preserve_center,
            _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def apply_scientific_style(
    shape_id: int, role: str = "neutral", profile: str = "sci_compact",
    page: str = "", doc_name: str = "",
) -> str:
    """Apply a semantic compact-SCI style to an existing editable shape.

    Roles: input, output, backbone, decision, exit, auxiliary, highlight, safety,
    accept, reject, container, data_flow, and decision_flow. Multi-line text gets
    the profile's slightly larger font and 115% line spacing automatically.
    """
    try:
        return _ok(visio.apply_scientific_style(
            shape_id, role, profile, _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def draw_safe_orthogonal_connector(
    from_shape_id: int, to_shape_id: int,
    obstacle_ids: list[int] | None = None,
    preferred_axis: str = "auto", clearance: float = 0.12,
    role: str = "data_flow", profile: str = "sci_compact",
    enforce_clearance: bool = True,
    terminal_stub: float = 0.12,
    page: str = "", doc_name: str = "",
) -> str:
    """Draw an obstacle-aware native Visio orthogonal arrow.

    Use this instead of hand-authored polylines whenever a route passes near another
    module or text box. Connectors attach at side centers; their first and last
    segments are perpendicular to the control edge and remain straight for at least
    terminal_stub before any 90-degree turn. Rounded-corner attachments are avoided.
    """
    try:
        return _ok(visio.draw_safe_orthogonal_connector(
            from_shape_id, to_shape_id, obstacle_ids, preferred_axis, clearance,
            role, profile, enforce_clearance, terminal_stub,
            _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def audit_scientific_layout(
    min_control_gap: float = 0.14,
    connector_clearance: float = 0.04,
    min_connector_length: float = 0.12,
    terminal_stub: float = 0.12,
    corner_exclusion: float = 0.10,
    terminal_tolerance: float = 0.02,
    page: str = "", doc_name: str = "",
) -> str:
    """Audit spacing, crossings, corner attachments, and terminal geometry.

    This is mandatory before exporting compact scientific figures. Fix every error;
    warnings identify control gaps that are too small for reliable print rendering.
    """
    try:
        return _ok(visio.audit_scientific_layout(
            min_control_gap, connector_clearance, min_connector_length,
            terminal_stub, corner_exclusion, terminal_tolerance,
            _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def export_scientific_figure(
    output_paths: str, strict: bool = True,
    min_control_gap: float = 0.14,
    connector_clearance: float = 0.04,
    min_connector_length: float = 0.12,
    terminal_stub: float = 0.12,
    corner_exclusion: float = 0.10,
    terminal_tolerance: float = 0.02,
    page: str = "", doc_name: str = "",
) -> str:
    """Audit and export a scientific figure to one or more image paths.

    output_paths is a JSON list such as ["C:/out/figure.svg", "C:/out/figure.png"].
    Export is blocked on layout errors. With strict=true (default), warnings also block
    export, preventing touching controls, obscured arrowheads, and connector/text overlap.
    """
    try:
        page_ref = _parse_page(page)
        audit = visio.audit_scientific_layout(
            min_control_gap, connector_clearance, min_connector_length,
            terminal_stub, corner_exclusion, terminal_tolerance,
            page_ref, doc_name,
        )
        blocked = audit["errors"] > 0 or (strict and audit["warnings"] > 0)
        if blocked:
            return _ok({
                "exported": False,
                "reason": "layout_audit_failed",
                "audit": audit,
            })
        paths = json.loads(output_paths)
        if not isinstance(paths, list) or not paths:
            raise ValueError("output_paths must be a non-empty JSON list")
        exported = [visio.export_page_as_image(path, page_ref, doc_name) for path in paths]
        return _ok({"exported": True, "audit": audit, "outputs": exported})
    except Exception as e:
        return _err(e)


@mcp.tool()
def batch_update_shapes(
    updates: str, page: str = "", doc_name: str = "",
) -> str:
    """Quickly update many shapes in one call.

    Each JSON object requires shape_id and may include text, x, y, width, height,
    angle, any set_shape_format field, or a nested format object.

    Example:
      [{"shape_id":5,"x":3.2,"fill_color":"RGB(230,240,250)"},
       {"shape_id":8,"line_pattern":"dashed","end_arrow":"standard"}]
    """
    try:
        return _ok(visio.batch_update_shapes(
            json.loads(updates), _parse_page(page), doc_name,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def delete_shape(
    shape_id: int,
    page: str = "", doc_name: str = "",
) -> str:
    """Delete a shape by ID.

    Args:
        shape_id: Shape ID.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.delete_shape(shape_id, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def group_shapes(
    shape_ids: list[int],
    page: str = "", doc_name: str = "",
) -> str:
    """Group multiple shapes together.

    Args:
        shape_ids: List of shape IDs to group.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.group_shapes(shape_ids, page_ref, doc_name))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Batch Operations
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def batch_draw_shapes(
    shapes: str,
    page: str = "",
    doc_name: str = "",
    style_profile: str = "sci_compact",
    default_role: str = "neutral",
) -> str:
    """Create multiple shapes in one call. MUCH faster than individual drop_shape calls.

    IMPORTANT: For standard diagram types, you MUST first call create_diagram(diagram_type)
    to create the document, then use the exact master names and stencils from the standard
    returned by create_diagram() or get_diagram_standard(). Do NOT use draw_rectangle/draw_oval
    as substitutes for standard stencil shapes.

    Args:
        shapes: JSON array of shape definitions. Each object can have:
            - id: Local ref string for use in batch_connect_shapes (e.g. "start", "step1")
            - type: "drop" (default), "rectangle", "rounded_rectangle", "text_box",
              "oval", "line", "polyline", "diamond", "regular_polygon", "arc", "bezier",
              "quarter_arc", "spline", or "nurbs"
            - For "drop": master_name, stencil_name, x, y
            - For "rectangle"/"oval": x1, y1, x2, y2
            - For "line": x1, y1, x2, y2
            - For "polyline": points (flat [x1,y1,...]), optional flags (0=open, 1=fill)
            - For "regular_polygon": center_x, center_y, radius, sides, optional rotation
            - For "diamond": center_x, center_y, optional width and height. The SCI
              default is a compact, flat 1.20 x 0.54 in decision diamond.
            - For "arc": x1, y1, x2, y2, control_x, control_y
            - For "bezier": points (flat [x1,y1,...]), optional degree (default 3), optional flags
            - For "quarter_arc": x1, y1, x2, y2, optional sweep (0=convex, 1=concave)
            - For "spline": points (flat [x1,y1,...]), optional tolerance, optional flags
            - For "nurbs": control_points (flat [x1,y1,...]), knots, optional degree (default 3), optional weights
            - Optional: text, width, height
            - Optional formatting: fill_color, fill_pattern, transparency,
              line_color, line_weight, line_pattern, begin_arrow, end_arrow,
              arrow sizes, line cap/rounding, font name/size/color, bold/italic,
              text alignment/margins, line_spacing, paragraph_before/after,
              rotation angle, and connector routing.
            - semantic_role: input, output, backbone, decision, exit, auxiliary,
              highlight, safety, accept, reject, container, data_flow, decision_flow.

            With the default sci_compact profile, omitted colors, font properties,
            margins, and line styles are filled from the print-friendly journal style.
            Multi-line text defaults to 10 pt with 115% line spacing. Explicit values
            always win. Prefer edge gaps of 0.16 in vertically and 0.18 in horizontally.

            Lines and connectors MUST use begin_arrow/end_arrow for arrows; do not
            create separate triangle or polygon shapes as arrowheads.

            Do not hand-route a polyline through or immediately beside a control/text
            box. Use draw_safe_orthogonal_connector for obstacle-aware branches.
            After all shapes and connectors are created, call audit_scientific_layout;
            use export_scientific_figure to prevent exporting a page with collisions.

            Example: [{"id":"s1","type":"drop","master_name":"Process","stencil_name":"FLOWM_M.vssx","x":4,"y":8,"text":"Step 1"}]
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.

    Returns:
        JSON with ref_map (id->shape_id mapping) and shapes list.
        Pass the ref_map to batch_connect_shapes to wire up connections.
    """
    try:
        shapes_list = json.loads(shapes)
        page_ref = _parse_page(page)
        return _ok(visio.batch_draw_shapes(
            shapes_list, page_ref, doc_name, style_profile, default_role,
        ))
    except Exception as e:
        return _err(e)


@mcp.tool()
def batch_connect_shapes(
    connections: str,
    ref_map: str = "{}",
    page: str = "",
    doc_name: str = "",
    style_profile: str = "sci_compact",
    default_role: str = "data_flow",
    enforce_clearance: bool = True,
    min_clearance: float = 0.14,
    enforce_perpendicular: bool = True,
    terminal_stub: float = 0.12,
) -> str:
    """Connect multiple shape pairs in one call.

    For standard diagram types (UML, BPMN, ERD, etc.), each connection MUST specify
    connector_master and connector_stencil as defined by get_diagram_standard().
    Without these, AutoConnect produces generic arrows without correct UML/BPMN semantics.

    Args:
        connections: JSON array of connection objects, each with:
            - from: ref ID string (from batch_draw_shapes) or integer shape ID
            - to: ref ID string or integer shape ID
            - connector_master: (optional) Connector master name from stencil
            - connector_stencil: (optional) Stencil file for the connector
            - from_port: (optional) Connection point row index on source shape.
                         Glues to a specific connection point instead of PinX.
                         Essential for sequence diagrams (attach to lifeline).
            - to_port: (optional) Connection point row index on target shape.
            - line_color, line_weight, line_pattern ("solid"/"dashed")
            - begin_arrow, end_arrow (native Visio style 0-45 or "standard")
            - begin_arrow_size, end_arrow_size, line_cap, rounding
            - route_style and connector_appearance
            - semantic_role: data_flow or decision_flow. The latter automatically
              uses the native orange dashed SCI decision style.

            With enforce_clearance=true, touching or near-touching free-form controls
            are automatically separated to min_clearance before AutoConnect runs, so
            native arrowheads remain visible. Stencil-specific semantic connectors are
            never moved automatically.

            With enforce_perpendicular=true, misaligned free-form connections are
            forced to right-angle routing. The scientific layout audit then blocks
            corner attachments, non-perpendicular terminals, and bends closer than
            terminal_stub to either control.

            Example (UML): [{"from":"dog","to":"animal","connector_master":"Inheritance","connector_stencil":"USTRME_M.VSSX"}]
            Example (free-form solid arrow): [{"from":"s1","to":"s2","line_pattern":"solid","end_arrow":"standard"}]
            Example (decision flow): [{"from":"d1","to":"e1","line_pattern":"dashed","line_color":"RGB(180,120,40)","end_arrow":"standard"}]
            Example (sequence): [{"from":"client","to":"auth","from_port":1,"to_port":1,"connector_master":"Message","connector_stencil":"USEQME_M.VSSX"}]
        ref_map: JSON object mapping ref IDs to Visio shape IDs.
                 Use the ref_map returned by batch_draw_shapes.
                 Example: {"s1":5,"s2":6,"s3":7}
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.

    Returns:
        JSON array of connector shape info.
    """
    try:
        conn_list = json.loads(connections)
        id_map = json.loads(ref_map)
        # Ensure values are int
        id_map = {k: int(v) for k, v in id_map.items()}
        page_ref = _parse_page(page)
        return _ok(visio.batch_connect_shapes(
            conn_list, id_map, page_ref, doc_name, style_profile, default_role,
            enforce_clearance, min_clearance, enforce_perpendicular, terminal_stub,
        ))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Read / Analysis
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def list_shapes(page: str = "", doc_name: str = "") -> str:
    """List all shapes on a page with their IDs, names, text, and positions.

    Args:
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.list_shapes(page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_shape_info(
    shape_id: int,
    page: str = "", doc_name: str = "",
) -> str:
    """Get detailed information about a shape (position, size, colors, text).

    Args:
        shape_id: Shape ID.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.get_shape_info(shape_id, page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_connections(page: str = "", doc_name: str = "") -> str:
    """Get all connections between shapes on a page.

    Args:
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.get_connections(page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def get_page_summary(page: str = "", doc_name: str = "") -> str:
    """Get a summary of the page: shape count, connections, etc.

    Args:
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.get_page_summary(page_ref, doc_name))
    except Exception as e:
        return _err(e)


@mcp.tool()
def read_shape_data(
    shape_id: int,
    page: str = "", doc_name: str = "",
) -> str:
    """Read custom Shape Data (properties) from a shape.

    Args:
        shape_id: Shape ID.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.read_shape_data(shape_id, page_ref, doc_name))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Stencils / Masters
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def list_stencils() -> str:
    """List all currently open stencils."""
    try:
        return _ok(visio.list_stencils())
    except Exception as e:
        return _err(e)


@mcp.tool()
def open_stencil(stencil_path: str) -> str:
    """Open a stencil file.

    Args:
        stencil_path: Stencil file name (e.g. 'BASIC_M.vssx') or full path.
    """
    try:
        return _ok(visio.open_stencil(stencil_path))
    except Exception as e:
        return _err(e)


@mcp.tool()
def list_masters(stencil_name: str) -> str:
    """List all master shapes in a stencil.

    Args:
        stencil_name: Stencil name or path.
    """
    try:
        return _ok(visio.list_masters(stencil_name))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Export
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def export_page_as_image(
    output_path: str,
    page: str = "", doc_name: str = "",
) -> str:
    """Export a page as an image file (PNG, SVG, JPG, etc.).

    Args:
        output_path: Output file path. Format determined by extension.
        page: Page name or index. Empty for active page.
        doc_name: Document name. Empty for active document.
    """
    try:
        page_ref = _parse_page(page)
        return _ok(visio.export_page_as_image(output_path, page_ref, doc_name))
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Diagram Standards (Tools)
# ═══════════════════════════════════════════════════════════════════


@mcp.tool()
def list_diagram_types() -> str:
    """List all available diagram types with their IDs, names, templates, and standards.

    Returns a JSON array. Use the 'id' field with create_diagram() or get_diagram_standard().
    """
    return _ok(list_types())


@mcp.tool()
def get_diagram_standard(diagram_type: str) -> str:
    """Get the full drawing standard for a diagram type.

    Returns template, stencils, shapes, edges/connectors, and layout conventions.
    IMPORTANT: Always use create_diagram() to create a new document — it automatically
    applies the correct Visio template for the diagram type.

    Args:
        diagram_type: Diagram type ID (from list_diagram_types), e.g. 'class_diagram',
                      'sequence_diagram', 'flowchart', 'bpmn', 'erd_crows_foot',
                      'network_diagram', 'azure_architecture', 'kubernetes', 'org_chart'.
    """
    std = get_standard(diagram_type)
    if std is None:
        available = [t["id"] for t in list_types()]
        return _ok({"error": f"Unknown diagram type: {diagram_type}", "available_types": available})
    return _ok(std)


@mcp.tool()
def create_diagram(diagram_type: str) -> str:
    """Create a new Visio document using the standard template for a diagram type.

    This is the REQUIRED way to start drawing any diagram. It creates a document from
    the correct Visio template, which pre-loads the appropriate stencils, page settings,
    and styles for the diagram type.

    The response includes the full drawing standard (shapes, edges, layout, and a
    complete example) — use these exact master names and stencils when drawing.

    Args:
        diagram_type: Diagram type ID (from list_diagram_types), e.g. 'class_diagram',
                      'sequence_diagram', 'flowchart', 'bpmn', 'erd_crows_foot',
                      'network_diagram', 'azure_architecture', 'kubernetes', 'org_chart'.

    Returns:
        JSON with document info and the full drawing standard (shapes, edges, layout, example).
    """
    std = get_standard(diagram_type)
    if std is None:
        available = [t["id"] for t in list_types()]
        return _ok({"error": f"Unknown diagram type: {diagram_type}", "available_types": available})
    try:
        template = std["template"]
        result = visio.create_document(template)
        result["diagram_type"] = diagram_type
        result["template"] = template
        # Embed the full standard so the caller knows exactly which shapes/edges to use
        result["standard"] = {
            "shapes": std.get("shapes", []),
            "edges": std.get("edges", []),
            "layout": std.get("layout", {}),
            "example": std.get("example", {}),
            "stencils": std.get("stencils", []),
        }
        result["instructions"] = (
            "MANDATORY: Use ONLY the master names and stencils listed in 'standard.shapes' "
            "and 'standard.edges' above. For connections, specify connector_master and "
            "connector_stencil in batch_connect_shapes — do NOT use plain AutoConnect "
            "unless the standard's edges say so. See 'standard.example' for a complete "
            "working example with exact batch_draw_shapes/batch_connect_shapes parameters."
        )
        return _ok(result)
    except Exception as e:
        return _err(e)


# ═══════════════════════════════════════════════════════════════════
# Diagram Standards (Resources)
# ═══════════════════════════════════════════════════════════════════


@mcp.resource("visio://standards")
def standards_index() -> str:
    """Index of all available diagram type standards."""
    return json.dumps(list_types(), ensure_ascii=False, indent=2)


@mcp.resource("visio://standards/{diagram_type}")
def standard_detail(diagram_type: str) -> str:
    """Full drawing standard for a specific diagram type."""
    std = get_standard(diagram_type)
    if std is None:
        return json.dumps({"error": f"Unknown diagram type: {diagram_type}"}, ensure_ascii=False)
    return json.dumps(std, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════


def _parse_page(page: str):
    """Parse page parameter: empty -> None, numeric string -> int, else str."""
    if not page:
        return None
    try:
        return int(page)
    except ValueError:
        return page


if __name__ == "__main__":
    mcp.run(transport="stdio")
