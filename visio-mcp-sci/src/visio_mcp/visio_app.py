"""Visio COM automation wrapper."""

import sys
import logging
import math
import copy
import pythoncom
import win32com.client

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)

# Visio constants
visOpenRO = 2
visOpenMinimized = 16
visSaveAsWS = 0
visDelete = 0

# Shape type constants
visTypeShape = 1
visTypeGroup = 2
visTypeForeignObject = 4

# Section/Row/Cell indices for ShapeSheet
visSectionObject = 1
visRowXFormOut = 1
visSectionProp = 243  # visSectionProp

# Cell indices
visXFormPinX = 0
visXFormPinY = 1
visXFormWidth = 2
visXFormHeight = 3

# Connect constants
visAutoConnectDirNone = 0


# ShapeSheet line-format aliases. Numeric strings are also accepted directly,
# which keeps the full Visio range available (arrowhead styles 0-45).
_LINE_PATTERN_ALIASES = {
    "solid": "1",
    "dash": "2",
    "dashed": "2",
}

_ARROW_ALIASES = {
    "none": "0",
    "arrow": "4",
    "standard": "4",
    "filled": "4",
    "filled_arrow": "4",
}

_LINE_CAP_ALIASES = {"round": "0", "rounded": "0", "square": "1", "extended": "2"}
_FILL_PATTERN_ALIASES = {"none": "0", "solid": "1"}
_H_ALIGN_ALIASES = {
    "left": "0", "center": "1", "centre": "1", "right": "2",
    "justify": "3", "force": "4", "force_justify": "4",
}
_V_ALIGN_ALIASES = {"top": "0", "middle": "1", "center": "1", "bottom": "2"}
_ROUTE_STYLE_ALIASES = {
    "default": "0", "right_angle": "1", "orthogonal": "1", "straight": "2",
    "org_chart_down": "3", "org_chart_right": "4",
    "flowchart_down": "5", "flowchart_right": "6",
    "tree_down": "7", "tree_right": "8", "network": "9",
    "center_to_center": "16", "simple_down": "17", "simple_right": "18",
    "simple_up": "19", "simple_left": "20", "simple_hv": "21", "simple_vh": "22",
}
_CONNECTOR_APPEARANCE_ALIASES = {"default": "0", "straight": "1", "curved": "2"}


# Print-friendly, colorblind-conscious defaults for compact scientific figures.
# Pale fills remain distinguishable in grayscale; darker borders carry semantics.
SCIENTIFIC_STYLE_PROFILES = {
    "sci_compact": {
        "name": "Compact SCI / IEEE",
        "description": (
            "Compact, editable vector styling for IEEE, Elsevier, Springer Nature, "
            "and other high-impact scientific journals. No gradients or shadows."
        ),
        "palette": {
            "ink": "RGB(43,52,61)",
            "frame": "RGB(111,121,130)",
            "backbone_fill": "RGB(229,238,248)",
            "backbone_line": "RGB(68,105,148)",
            "decision_fill": "RGB(250,241,228)",
            "decision_line": "RGB(190,119,55)",
            "auxiliary_fill": "RGB(235,239,244)",
            "auxiliary_line": "RGB(91,106,125)",
            "highlight_fill": "RGB(232,242,240)",
            "highlight_line": "RGB(47,119,111)",
            "accept_fill": "RGB(229,242,233)",
            "accept_line": "RGB(54,130,84)",
            "reject_fill": "RGB(247,232,233)",
            "reject_line": "RGB(177,72,82)",
            "white": "RGB(255,255,255)",
        },
        "typography": {
            "font_name": "Arial",
            "body_font_size": "9.5 pt",
            "multiline_font_size": "10 pt",
            "title_font_size": "11 pt",
            "note_font_size": "8.5 pt",
            "line_spacing": "115%",
            "paragraph_before": "0.5 pt",
            "paragraph_after": "0.5 pt",
        },
        "geometry": {
            "node_width": 1.45,
            "node_height": 0.46,
            "multiline_height": 0.72,
            "diamond_width": 1.20,
            "diamond_height": 0.54,
            "horizontal_gap": 0.18,
            "vertical_gap": 0.16,
            "panel_gap": 0.18,
            "outer_margin": 0.18,
            "min_control_gap": 0.14,
            "connector_clearance": 0.12,
            "label_clearance": 0.10,
            "min_connector_length": 0.12,
            "terminal_stub": 0.0,
            "corner_exclusion": 0.10,
            "terminal_tolerance": 0.02,
            "text_margin": "0.05 in",
            "corner_rounding": "0.06 in",
        },
        "aesthetic_rules": [
            "Use editable vector shapes with no gradients, shadows, or decorative effects.",
            "Prefer short, clean native Visio connectors over hand-made arrow geometry.",
            "Use side-normal terminal stubs only when they improve clarity in dense routing.",
            "Minimize excess whitespace and use no more than four functional hues per panel where practical.",
        ],
        "lines": {
            "data_color": "RGB(43,52,61)",
            "data_weight": "1.1 pt",
            "decision_color": "RGB(190,119,55)",
            "decision_weight": "1 pt",
            "arrow": "standard",
            "arrow_size": "2",
        },
        "roles": {
            "neutral": {"fill_color": "RGB(255,255,255)", "line_color": "RGB(111,121,130)"},
            "input": {"fill_color": "RGB(255,255,255)", "line_color": "RGB(111,121,130)"},
            "output": {"fill_color": "RGB(255,255,255)", "line_color": "RGB(111,121,130)"},
            "backbone": {"fill_color": "RGB(229,238,248)", "line_color": "RGB(68,105,148)"},
            "decision": {"fill_color": "RGB(250,241,228)", "line_color": "RGB(190,119,55)"},
            "exit": {"fill_color": "RGB(250,241,228)", "line_color": "RGB(190,119,55)"},
            "auxiliary": {"fill_color": "RGB(235,239,244)", "line_color": "RGB(91,106,125)"},
            "highlight": {"fill_color": "RGB(232,242,240)", "line_color": "RGB(47,119,111)"},
            "safety": {"fill_color": "RGB(235,239,244)", "line_color": "RGB(91,106,125)"},
            "accept": {"fill_color": "RGB(229,242,233)", "line_color": "RGB(54,130,84)"},
            "reject": {"fill_color": "RGB(247,232,233)", "line_color": "RGB(177,72,82)"},
            "container": {"fill_color": "RGB(255,255,255)", "line_color": "RGB(150,158,165)", "line_weight": "0.7 pt"},
            "data_flow": {"line_color": "RGB(43,52,61)", "line_pattern": "solid", "line_weight": "1.1 pt", "end_arrow": "standard", "end_arrow_size": "2"},
            "decision_flow": {"line_color": "RGB(190,119,55)", "line_pattern": "dashed", "line_weight": "1 pt", "end_arrow": "standard", "end_arrow_size": "2"},
        },
    },
}


def _register_palette_profile(key: str, name: str, description: str, palette: dict[str, str]) -> None:
    spec = copy.deepcopy(SCIENTIFIC_STYLE_PROFILES["sci_compact"])
    spec["name"] = name
    spec["description"] = description
    spec["palette"].update(palette)
    spec["roles"].update({
        "neutral": {"fill_color": palette["white"], "line_color": palette["frame"]},
        "input": {"fill_color": palette["white"], "line_color": palette["frame"]},
        "output": {"fill_color": palette["white"], "line_color": palette["frame"]},
        "backbone": {"fill_color": palette["backbone_fill"], "line_color": palette["backbone_line"]},
        "decision": {"fill_color": palette["decision_fill"], "line_color": palette["decision_line"]},
        "exit": {"fill_color": palette["decision_fill"], "line_color": palette["decision_line"]},
        "auxiliary": {"fill_color": palette["auxiliary_fill"], "line_color": palette["auxiliary_line"]},
        "highlight": {"fill_color": palette["highlight_fill"], "line_color": palette["highlight_line"]},
        "safety": {"fill_color": palette["auxiliary_fill"], "line_color": palette["auxiliary_line"]},
        "accept": {"fill_color": palette["accept_fill"], "line_color": palette["accept_line"]},
        "reject": {"fill_color": palette["reject_fill"], "line_color": palette["reject_line"]},
        "container": {"fill_color": palette["white"], "line_color": palette["container_line"], "line_weight": "0.7 pt"},
        "data_flow": {
            "line_color": palette["ink"], "line_pattern": "solid",
            "line_weight": "1.1 pt", "end_arrow": "standard", "end_arrow_size": "2",
        },
        "decision_flow": {
            "line_color": palette["decision_line"], "line_pattern": "dashed",
            "line_weight": "1 pt", "end_arrow": "standard", "end_arrow_size": "2",
        },
    })
    spec["lines"]["data_color"] = palette["ink"]
    spec["lines"]["decision_color"] = palette["decision_line"]
    SCIENTIFIC_STYLE_PROFILES[key] = spec


_register_palette_profile(
    "sci_nature",
    "Nature-style muted colorblind palette",
    "Muted blue, ochre, teal, gray, green, and vermillion for editable Nature-style figures.",
    {
        "ink": "RGB(36,49,60)", "frame": "RGB(126,136,144)",
        "backbone_fill": "RGB(225,236,247)", "backbone_line": "RGB(79,117,157)",
        "decision_fill": "RGB(250,240,226)", "decision_line": "RGB(196,124,49)",
        "auxiliary_fill": "RGB(232,237,243)", "auxiliary_line": "RGB(96,112,130)",
        "highlight_fill": "RGB(228,242,239)", "highlight_line": "RGB(48,128,119)",
        "accept_fill": "RGB(229,243,234)", "accept_line": "RGB(59,134,88)",
        "reject_fill": "RGB(248,231,231)", "reject_line": "RGB(184,80,83)",
        "container_line": "RGB(159,168,176)", "white": "RGB(255,255,255)",
    },
)
_register_palette_profile(
    "sci_ieee",
    "IEEE restrained blue-gray palette",
    "Low-saturation blue-gray palette for engineering framework diagrams and grayscale robustness.",
    {
        "ink": "RGB(38,47,56)", "frame": "RGB(128,136,143)",
        "backbone_fill": "RGB(226,234,243)", "backbone_line": "RGB(76,105,139)",
        "decision_fill": "RGB(249,240,226)", "decision_line": "RGB(181,119,58)",
        "auxiliary_fill": "RGB(235,238,242)", "auxiliary_line": "RGB(94,104,116)",
        "highlight_fill": "RGB(230,241,238)", "highlight_line": "RGB(58,119,108)",
        "accept_fill": "RGB(231,242,235)", "accept_line": "RGB(69,128,89)",
        "reject_fill": "RGB(247,233,234)", "reject_line": "RGB(170,78,88)",
        "container_line": "RGB(160,166,172)", "white": "RGB(255,255,255)",
    },
)
_register_palette_profile(
    "sci_cell",
    "Cell-style soft categorical palette",
    "Soft categorical palette with teal emphasis, blue structure, amber decisions, and restrained red/green outcomes.",
    {
        "ink": "RGB(38,45,52)", "frame": "RGB(124,135,142)",
        "backbone_fill": "RGB(224,237,245)", "backbone_line": "RGB(66,111,150)",
        "decision_fill": "RGB(250,238,222)", "decision_line": "RGB(197,116,54)",
        "auxiliary_fill": "RGB(232,236,241)", "auxiliary_line": "RGB(84,101,116)",
        "highlight_fill": "RGB(226,242,238)", "highlight_line": "RGB(43,130,121)",
        "accept_fill": "RGB(229,243,235)", "accept_line": "RGB(63,136,92)",
        "reject_fill": "RGB(249,232,233)", "reject_line": "RGB(182,76,86)",
        "container_line": "RGB(158,166,173)", "white": "RGB(255,255,255)",
    },
)
_register_palette_profile(
    "sci_mono",
    "Monochrome print-safe palette",
    "Near-monochrome palette for journals or reviewers who prefer line-art style framework figures.",
    {
        "ink": "RGB(45,49,54)", "frame": "RGB(120,126,132)",
        "backbone_fill": "RGB(235,239,244)", "backbone_line": "RGB(82,92,105)",
        "decision_fill": "RGB(247,244,239)", "decision_line": "RGB(116,98,77)",
        "auxiliary_fill": "RGB(238,240,243)", "auxiliary_line": "RGB(101,108,117)",
        "highlight_fill": "RGB(236,241,240)", "highlight_line": "RGB(85,110,106)",
        "accept_fill": "RGB(239,244,241)", "accept_line": "RGB(87,113,96)",
        "reject_fill": "RGB(244,239,240)", "reject_line": "RGB(124,91,95)",
        "container_line": "RGB(164,169,174)", "white": "RGB(255,255,255)",
    },
)


def get_scientific_style_profile(profile: str = "sci_compact") -> dict:
    """Return a detached scientific-style profile for MCP clients."""
    key = str(profile or "sci_compact").lower().replace("-", "_")
    if key not in SCIENTIFIC_STYLE_PROFILES:
        raise ValueError(f"Unknown scientific style profile: {profile}")
    source = SCIENTIFIC_STYLE_PROFILES[key]
    return copy.deepcopy(source)


def _scientific_defaults(defn: dict, profile: str = "", default_role: str = "neutral") -> dict:
    """Merge compact SCI defaults without overriding explicitly supplied values."""
    if not profile:
        return dict(defn)
    spec = get_scientific_style_profile(profile)
    result = dict(defn)
    stype = str(result.get("type") or "drop").lower()
    role = str(result.get("semantic_role") or default_role or "neutral").lower().replace("-", "_")
    if stype in {"line", "polyline", "arc", "bezier", "quarter_arc", "spline", "nurbs"} and role == "neutral":
        role = "data_flow"
    role_style = spec["roles"].get(role, spec["roles"]["neutral"])
    if stype != "text_box" or result.get("semantic_role"):
        for key, value in role_style.items():
            if result.get(key) in (None, ""):
                result[key] = value

    text = str(result.get("text") or "")
    typography = spec["typography"]
    geometry = spec["geometry"]
    is_line = stype in {"line", "polyline", "arc", "bezier", "quarter_arc", "spline", "nurbs"}
    if not is_line:
        if stype != "text_box" or result.get("semantic_role"):
            result.setdefault("fill_pattern", "solid")
            result.setdefault("line_pattern", "solid")
            result.setdefault("line_weight", "0.85 pt")
        result.setdefault("font_name", typography["font_name"])
        result.setdefault(
            "font_size",
            typography["multiline_font_size"] if "\n" in text else typography["body_font_size"],
        )
        result.setdefault("font_color", spec["palette"]["ink"])
        result.setdefault("h_align", "center")
        result.setdefault("v_align", "middle")
        result.setdefault("line_spacing", typography["line_spacing"])
        result.setdefault("paragraph_before", typography["paragraph_before"])
        result.setdefault("paragraph_after", typography["paragraph_after"])
        for margin_key in (
            "text_margin_left", "text_margin_right", "text_margin_top", "text_margin_bottom",
        ):
            result.setdefault(margin_key, geometry["text_margin"])
        if stype == "rounded_rectangle":
            result.setdefault("rounding", geometry["corner_rounding"])
    return result


def _line_formula(value, aliases: dict[str, str]) -> str:
    """Convert a friendly line-format value to a Visio formula string."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return str(int(value))
    text = str(value).strip()
    return aliases.get(text.lower().replace("-", "_"), text)


def _length_formula(value) -> str:
    """Use inches for numeric length values; preserve explicit formulas/units."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{value} in"
    return str(value).strip()


def _percent_formula(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{value}%"
    return str(value).strip()


def _line_spacing_formula(value) -> str:
    """Convert friendly positive percentages to Visio's negative relative-spacing form."""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        if value == 0:
            return "0"
        return f"-{abs(value)}%"
    text = str(value).strip()
    if text.endswith("%") and not text.startswith("-"):
        return f"-{text}"
    return text


def _angle_formula(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        return f"{value} deg"
    return str(value).strip()


def _apply_line_format(
    shape,
    line_color: str = "",
    line_weight: str = "",
    line_pattern="",
    begin_arrow="",
    end_arrow="",
    begin_arrow_size="",
    end_arrow_size="",
    line_transparency="",
    line_cap="",
    rounding="",
    route_style="",
    connector_appearance="",
) -> None:
    """Apply native Visio line and arrowhead formatting to a shape."""
    if line_color:
        shape.CellsU("LineColor").FormulaU = line_color
    if line_weight:
        shape.CellsU("LineWeight").FormulaU = line_weight

    pattern = _line_formula(line_pattern, _LINE_PATTERN_ALIASES)
    if pattern:
        shape.CellsU("LinePattern").FormulaU = pattern

    begin = _line_formula(begin_arrow, _ARROW_ALIASES)
    if begin:
        shape.CellsU("BeginArrow").FormulaU = begin

    end = _line_formula(end_arrow, _ARROW_ALIASES)
    if end:
        shape.CellsU("EndArrow").FormulaU = end

    if begin_arrow_size not in (None, ""):
        shape.CellsU("BeginArrowSize").FormulaU = str(begin_arrow_size)
    if end_arrow_size not in (None, ""):
        shape.CellsU("EndArrowSize").FormulaU = str(end_arrow_size)

    if line_transparency not in (None, ""):
        shape.CellsU("LineColorTrans").FormulaU = _percent_formula(line_transparency)

    cap = _line_formula(line_cap, _LINE_CAP_ALIASES)
    if cap:
        shape.CellsU("LineCap").FormulaU = cap

    rounding_formula = _length_formula(rounding)
    if rounding_formula:
        shape.CellsU("Rounding").FormulaU = rounding_formula

    route = _line_formula(route_style, _ROUTE_STYLE_ALIASES)
    if route:
        shape.CellsU("ShapeRouteStyle").FormulaU = route

    appearance = _line_formula(connector_appearance, _CONNECTOR_APPEARANCE_ALIASES)
    if appearance:
        shape.CellsU("ConLineRouteExt").FormulaU = appearance


def _apply_fill_format(
    shape,
    fill_color: str = "",
    fill_background_color: str = "",
    fill_pattern="",
    fill_transparency="",
    fill_background_transparency="",
) -> None:
    if fill_color:
        shape.CellsU("FillForegnd").FormulaU = fill_color
    if fill_background_color:
        shape.CellsU("FillBkgnd").FormulaU = fill_background_color
    pattern = _line_formula(fill_pattern, _FILL_PATTERN_ALIASES)
    if pattern:
        shape.CellsU("FillPattern").FormulaU = pattern
    if fill_transparency not in (None, ""):
        shape.CellsU("FillForegndTrans").FormulaU = _percent_formula(fill_transparency)
    if fill_background_transparency not in (None, ""):
        shape.CellsU("FillBkgndTrans").FormulaU = _percent_formula(fill_background_transparency)


def _apply_text_format(
    shape,
    font_name: str = "",
    font_size: str = "",
    font_color: str = "",
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    h_align="",
    v_align="",
    text_margin_left="",
    text_margin_right="",
    text_margin_top="",
    text_margin_bottom="",
    text_background_color: str = "",
    text_background_transparency="",
    line_spacing="",
    paragraph_before="",
    paragraph_after="",
) -> None:
    if font_name:
        escaped = str(font_name).replace('"', '""')
        shape.CellsU("Char.Font").FormulaU = f'FONT("{escaped}")'
    if font_size:
        shape.CellsU("Char.Size").FormulaU = font_size
    if font_color:
        shape.CellsU("Char.Color").FormulaU = font_color

    if any(value is not None for value in (bold, italic, underline)):
        cell = shape.CellsU("Char.Style")
        try:
            style = int(cell.ResultIU)
        except Exception:
            style = 0
        for enabled, mask in ((bold, 1), (italic, 2), (underline, 4)):
            if enabled is True:
                style |= mask
            elif enabled is False:
                style &= ~mask
        cell.FormulaU = str(style)

    horizontal = _line_formula(h_align, _H_ALIGN_ALIASES)
    if horizontal:
        shape.CellsU("Para.HorzAlign").FormulaU = horizontal
    vertical = _line_formula(v_align, _V_ALIGN_ALIASES)
    if vertical:
        shape.CellsU("VerticalAlign").FormulaU = vertical

    for cell_name, value in (
        ("LeftMargin", text_margin_left), ("RightMargin", text_margin_right),
        ("TopMargin", text_margin_top), ("BottomMargin", text_margin_bottom),
    ):
        formula = _length_formula(value)
        if formula:
            shape.CellsU(cell_name).FormulaU = formula

    if text_background_color:
        shape.CellsU("TextBkgnd").FormulaU = text_background_color
    if text_background_transparency not in (None, ""):
        shape.CellsU("TextBkgndTrans").FormulaU = _percent_formula(text_background_transparency)

    # Paragraph cells keep multi-line scientific labels readable at compact sizes.
    # Percentage values are accepted for line spacing; point values suit paragraph gaps.
    if line_spacing not in (None, ""):
        shape.CellsU("Para.SpLine").FormulaU = _line_spacing_formula(line_spacing)
    for cell_name, value in (
        ("Para.SpBefore", paragraph_before),
        ("Para.SpAfter", paragraph_after),
    ):
        formula = _length_formula(value)
        if formula:
            shape.CellsU(cell_name).FormulaU = formula


class VisioApp:
    """Singleton wrapper around Visio COM Application object."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._app = None
        return cls._instance

    @property
    def app(self):
        """Get or create Visio Application COM object."""
        if self._app is None:
            self._ensure_app()
        return self._app

    def _ensure_app(self):
        """Start or connect to Visio application."""
        pythoncom.CoInitialize()
        try:
            self._app = win32com.client.GetActiveObject("Visio.Application")
            logger.info("Connected to existing Visio instance")
        except Exception:
            self._app = win32com.client.Dispatch("Visio.Application")
            self._app.Visible = True
            logger.info("Started new Visio instance")

    # ── Document Management ──────────────────────────────────────────

    def create_document(self, template: str = "") -> dict:
        """Create a new Visio document.

        Args:
            template: Optional template path or built-in template name.
                      Empty string creates a blank document.
        Returns:
            dict with document info (name, index, pages count).
        """
        doc = self.app.Documents.Add(template)
        return {
            "name": doc.Name,
            "full_name": doc.FullName,
            "index": doc.Index,
            "pages": doc.Pages.Count,
        }

    def open_document(self, file_path: str) -> dict:
        """Open an existing Visio file."""
        doc = self.app.Documents.Open(file_path)
        return {
            "name": doc.Name,
            "full_name": doc.FullName,
            "index": doc.Index,
            "pages": doc.Pages.Count,
        }

    def save_document(self, doc_name: str = "") -> dict:
        """Save the specified or active document."""
        doc = self._get_document(doc_name)
        doc.Save()
        return {"name": doc.Name, "full_name": doc.FullName, "saved": True}

    def save_document_as(self, file_path: str, doc_name: str = "") -> dict:
        """Save the document to a new path."""
        doc = self._get_document(doc_name)
        doc.SaveAs(file_path)
        return {"name": doc.Name, "full_name": doc.FullName, "saved": True}

    def close_document(self, doc_name: str = "") -> dict:
        """Close the specified or active document."""
        doc = self._get_document(doc_name)
        name = doc.Name
        doc.Close()
        return {"closed": name}

    def list_open_documents(self) -> list[dict]:
        """List all open documents."""
        result = []
        for i in range(1, self.app.Documents.Count + 1):
            doc = self.app.Documents.Item(i)
            # Skip stencils (Type == 2)
            if doc.Type == 2:
                continue
            result.append({
                "name": doc.Name,
                "full_name": doc.FullName,
                "index": i,
                "pages": doc.Pages.Count,
            })
        return result

    # ── Page Operations ──────────────────────────────────────────────

    def list_pages(self, doc_name: str = "") -> list[dict]:
        """List all pages in a document."""
        doc = self._get_document(doc_name)
        result = []
        for i in range(1, doc.Pages.Count + 1):
            page = doc.Pages.Item(i)
            result.append({
                "name": page.Name,
                "index": i,
                "shapes_count": page.Shapes.Count,
            })
        return result

    def add_page(self, page_name: str = "", doc_name: str = "") -> dict:
        """Add a new page to the document."""
        doc = self._get_document(doc_name)
        page = doc.Pages.Add()
        if page_name:
            page.Name = page_name
        return {
            "name": page.Name,
            "index": page.Index,
        }

    def set_active_page(self, page_name_or_index, doc_name: str = "") -> dict:
        """Set the active page by name or index."""
        doc = self._get_document(doc_name)
        page = self._get_page(doc, page_name_or_index)
        self.app.ActiveWindow.Page = page
        return {"active_page": page.Name, "index": page.Index}

    def delete_page(self, page_name_or_index, doc_name: str = "") -> dict:
        """Delete a page."""
        doc = self._get_document(doc_name)
        page = self._get_page(doc, page_name_or_index)
        name = page.Name
        page.Delete(0)
        return {"deleted": name}

    # ── Shape Operations ─────────────────────────────────────────────

    def drop_shape(
        self,
        master_name: str,
        stencil_name: str,
        x: float,
        y: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Drop a master shape from a stencil onto the page.

        Args:
            master_name: Name of the master shape in the stencil.
            stencil_name: Stencil file name (e.g. 'BASIC_M.vssx').
            x, y: Position in inches.
            page_name_or_index: Target page (default: active page).
            doc_name: Target document (default: active document).
        Returns:
            dict with shape_id and name.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        stencil = self._open_stencil(stencil_name)
        master = stencil.Masters.ItemU(master_name)
        shape = page.Drop(master, x, y)
        return self._shape_info(shape)

    def draw_rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a rectangle. Coordinates in inches (x1,y1)=bottom-left, (x2,y2)=top-right."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawRectangle(x1, y1, x2, y2)
        return self._shape_info(shape)

    def draw_oval(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw an oval/ellipse. Bounding box in inches."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawOval(x1, y1, x2, y2)
        return self._shape_info(shape)

    def draw_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a line from (x1,y1) to (x2,y2) in inches."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawLine(x1, y1, x2, y2)
        return self._shape_info(shape)

    def draw_polyline(
        self,
        points: list[float],
        flags: int = 0,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a polyline (multi-segment line or closed polygon).

        Args:
            points: Flat array of coordinates [x1,y1, x2,y2, ...] in inches.
                    To close the polygon, repeat the first point at the end.
            flags: 0 = open polyline (default), 1 = fill shape (visPolyline1D).
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawPolyline(points, flags)
        return self._shape_info(shape)

    def draw_bezier(
        self,
        points: list[float],
        degree: int = 3,
        flags: int = 0,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a Bezier curve.

        Args:
            points: Flat array of control points [x1,y1, x2,y2, ...] in inches.
                    For degree 3: need 3n+1 points (start + groups of 3 control points).
            degree: 1 (linear), 2 (quadratic), or 3 (cubic, default).
            flags: 0 = default.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawBezier(points, degree, flags)
        return self._shape_info(shape)

    def draw_quarter_arc(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        sweep: int = 0,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a quarter-arc from (x1,y1) to (x2,y2).

        Args:
            x1, y1: Start point in inches.
            x2, y2: End point in inches.
            sweep: visArcSweepFlagConvex=0 (default) or visArcSweepFlagConcave=1.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        # visArcSweepFlagConvex = 0, visArcSweepFlagConcave = 1
        shape = page.DrawQuarterArc(x1, y1, x2, y2, sweep)
        return self._shape_info(shape)

    def draw_arc_by_three_points(
        self, x1: float, y1: float, x2: float, y2: float,
        control_x: float, control_y: float,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Draw a native editable Visio arc through begin, end, and control points."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawArcByThreePoints(x1, y1, x2, y2, control_x, control_y)
        return self._shape_info(shape)

    def draw_regular_polygon(
        self, center_x: float, center_y: float, radius: float, sides: int,
        rotation: float = 0.0, page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Draw a native editable regular polygon as a closed Visio polyline."""
        if sides < 3:
            raise ValueError("sides must be at least 3")
        page = self._resolve_page(doc_name, page_name_or_index)
        points: list[float] = []
        start = math.radians(rotation)
        for index in range(sides):
            angle = start + (2 * math.pi * index / sides)
            points.extend([
                center_x + radius * math.cos(angle),
                center_y + radius * math.sin(angle),
            ])
        points.extend(points[:2])
        shape = page.DrawPolyline(points, 1)
        return self._shape_info(shape)

    def draw_diamond(
        self, center_x: float, center_y: float,
        width: float = 1.20, height: float = 0.54,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Draw a compact, flat, native editable diamond decision shape."""
        if width <= 0 or height <= 0:
            raise ValueError("diamond width and height must be positive")
        page = self._resolve_page(doc_name, page_name_or_index)
        half_w, half_h = width / 2, height / 2
        points = [
            center_x - half_w, center_y,
            center_x, center_y + half_h,
            center_x + half_w, center_y,
            center_x, center_y - half_h,
            center_x - half_w, center_y,
        ]
        shape = page.DrawPolyline(points, 1)
        return self._shape_info(shape)

    def draw_spline(
        self,
        points: list[float],
        tolerance: float = 0.25,
        flags: int = 0,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a smooth spline through a set of points.

        Args:
            points: Flat array of coordinates [x1,y1, x2,y2, ...] in inches.
            tolerance: How closely the spline must follow the points (in inches).
                       Smaller = closer fit. Default 0.25.
            flags: 0 = default.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.DrawSpline(points, tolerance, flags)
        return self._shape_info(shape)

    def draw_nurbs(
        self,
        degree: int,
        control_points: list[float],
        knots: list[float],
        weights: list[float] | None = None,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Draw a NURBS curve.

        Args:
            degree: Degree of the curve (e.g. 3 for cubic).
            control_points: Flat array [x1,y1, x2,y2, ...] of control points in inches.
            knots: Knot vector (length = num_control_points + degree + 1).
            weights: Optional weight for each control point. All 1.0 if omitted.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        num_cp = len(control_points) // 2
        if weights is None:
            weights = [1.0] * num_cp

        # Visio DrawNURBS(degree, flags, xyArray, knots, weights)
        # flags: 0
        shape = page.DrawNURBS(degree, 0, control_points, knots, weights)
        return self._shape_info(shape)

    def connect_shapes(
        self,
        from_shape_id: int,
        to_shape_id: int,
        connector_master: str = "",
        connector_stencil: str = "",
        from_port: int = -1,
        to_port: int = -1,
        page_name_or_index=None,
        doc_name: str = "",
        line_color: str = "",
        line_weight: str = "",
        line_pattern="",
        begin_arrow="",
        end_arrow="",
        begin_arrow_size="",
        end_arrow_size="",
        line_transparency="",
        line_cap="",
        rounding="",
        route_style="",
        connector_appearance="",
    ) -> dict:
        """Connect two shapes with a dynamic connector.

        Args:
            from_shape_id: Source shape ID.
            to_shape_id: Target shape ID.
            connector_master: Connector master name (default: 'Dynamic connector').
            connector_stencil: Stencil for connector (default: built-in).
            from_port: Connection point row index on source shape (-1 = use PinX).
            to_port: Connection point row index on target shape (-1 = use PinX).
            line_pattern: Native Visio line pattern; "solid", "dashed", or a formula/index.
            begin_arrow: Native begin-arrow style (0-45, "none", or "standard").
            end_arrow: Native end-arrow style (0-45, "none", or "standard").
            begin_arrow_size: Native Visio BeginArrowSize value.
            end_arrow_size: Native Visio EndArrowSize value.
            line_transparency: Line transparency, e.g. "35%" or 35.
            line_cap: "round", "square", "extended", or a Visio index/formula.
            rounding: Connector corner rounding, e.g. "0.08 in".
            route_style: "right_angle", "straight", "simple_hv", etc.
            connector_appearance: "default", "straight", or "curved".
        Returns:
            dict with connector shape info.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        from_shape = page.Shapes.ItemFromID(from_shape_id)
        to_shape = page.Shapes.ItemFromID(to_shape_id)

        # Use AutoConnect if no custom connector specified
        if not connector_master:
            from_shape.AutoConnect(to_shape, visAutoConnectDirNone)
            # Find the connector that was just created (last shape)
            connector = page.Shapes.Item(page.Shapes.Count)
            _apply_line_format(
                connector, line_color, line_weight, line_pattern,
                begin_arrow, end_arrow, begin_arrow_size, end_arrow_size,
                line_transparency, line_cap, rounding, route_style,
                connector_appearance,
            )
            return self._shape_info(connector)

        stencil = self._open_stencil(connector_stencil)
        master = stencil.Masters.ItemU(connector_master)
        connector = page.Drop(master, 0, 0)

        # Glue begin to from_shape, end to to_shape
        # visSectionConnectionPts = 7
        if from_port >= 0:
            connector.CellsU("BeginX").GlueTo(from_shape.CellsSRC(7, from_port, 0))
        else:
            connector.CellsU("BeginX").GlueTo(from_shape.CellsU("PinX"))
        if to_port >= 0:
            connector.CellsU("EndX").GlueTo(to_shape.CellsSRC(7, to_port, 0))
        else:
            connector.CellsU("EndX").GlueTo(to_shape.CellsU("PinX"))

        _apply_line_format(
            connector, line_color, line_weight, line_pattern,
            begin_arrow, end_arrow, begin_arrow_size, end_arrow_size,
            line_transparency, line_cap, rounding, route_style,
            connector_appearance,
        )

        return self._shape_info(connector)

    def set_shape_text(
        self,
        shape_id: int,
        text: str,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Set the text content of a shape."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        shape.Text = text
        return self._shape_info(shape)

    def set_shape_format(
        self,
        shape_id: int,
        fill_color: str = "",
        line_color: str = "",
        line_weight: str = "",
        font_size: str = "",
        font_color: str = "",
        transparency: str = "",
        page_name_or_index=None,
        doc_name: str = "",
        line_pattern="",
        begin_arrow="",
        end_arrow="",
        begin_arrow_size="",
        end_arrow_size="",
        line_transparency="",
        line_cap="",
        rounding="",
        route_style="",
        connector_appearance="",
        fill_background_color: str = "",
        fill_pattern="",
        fill_background_transparency="",
        font_name: str = "",
        bold: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        h_align="",
        v_align="",
        text_margin_left="",
        text_margin_right="",
        text_margin_top="",
        text_margin_bottom="",
        text_background_color: str = "",
        text_background_transparency="",
        line_spacing="",
        paragraph_before="",
        paragraph_after="",
        angle="",
    ) -> dict:
        """Set formatting of a shape via ShapeSheet cells.

        Color values use Visio formulas, e.g.:
            - 'RGB(255,0,0)' for red
            - 'THEMEGUARD(RGB(255,0,0))'
        Line weight: e.g. '2 pt'
        Font size: e.g. '12 pt'
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)

        _apply_fill_format(
            shape, fill_color, fill_background_color, fill_pattern,
            transparency, fill_background_transparency,
        )
        _apply_line_format(
            shape, line_color, line_weight, line_pattern,
            begin_arrow, end_arrow, begin_arrow_size, end_arrow_size,
            line_transparency, line_cap, rounding, route_style,
            connector_appearance,
        )
        _apply_text_format(
            shape, font_name, font_size, font_color, bold, italic, underline,
            h_align, v_align, text_margin_left, text_margin_right,
            text_margin_top, text_margin_bottom, text_background_color,
            text_background_transparency, line_spacing,
            paragraph_before, paragraph_after,
        )
        angle_formula = _angle_formula(angle)
        if angle_formula:
            shape.CellsU("Angle").FormulaU = angle_formula

        return self._shape_info(shape)

    def move_shape(
        self,
        shape_id: int,
        x: float,
        y: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Move a shape to position (x, y) in inches."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        shape.CellsU("PinX").ResultIU = x
        shape.CellsU("PinY").ResultIU = y
        return self._shape_info(shape)

    def resize_shape(
        self,
        shape_id: int,
        width: float,
        height: float,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Resize a shape (width, height in inches)."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        shape.CellsU("Width").ResultIU = width
        shape.CellsU("Height").ResultIU = height
        return self._shape_info(shape)

    def set_page_size(
        self, width: float, height: float,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Set page size in inches for predictable paper-ready aspect ratios."""
        page = self._resolve_page(doc_name, page_name_or_index)
        page.PageSheet.CellsU("PageWidth").ResultIU = width
        page.PageSheet.CellsU("PageHeight").ResultIU = height
        return {"page_name": page.Name, "width": width, "height": height}

    def duplicate_shape(
        self, shape_id: int, offset_x: float = 0.25, offset_y: float = -0.25,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Duplicate a native Visio shape and offset the copy."""
        page = self._resolve_page(doc_name, page_name_or_index)
        original = page.Shapes.ItemFromID(shape_id)
        duplicate = original.Duplicate()
        duplicate.CellsU("PinX").ResultIU = original.CellsU("PinX").ResultIU + offset_x
        duplicate.CellsU("PinY").ResultIU = original.CellsU("PinY").ResultIU + offset_y
        return self._shape_info(duplicate)

    def set_z_order(
        self, shape_id: int, action: str,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Change z-order: bring_to_front, send_to_back, bring_forward, send_backward."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        actions = {
            "bring_to_front": "BringToFront",
            "send_to_back": "SendToBack",
            "bring_forward": "BringForward",
            "send_backward": "SendBackward",
        }
        method_name = actions.get(str(action).lower().replace("-", "_"))
        if not method_name:
            raise ValueError(f"Unknown z-order action: {action}")
        getattr(shape, method_name)()
        return self._shape_info(shape)

    def align_shapes(
        self, shape_ids: list[int], alignment: str, reference_shape_id: int = 0,
        page_name_or_index=None, doc_name: str = "",
    ) -> list[dict]:
        """Align native shapes without grouping them, preserving manual editability."""
        if len(shape_ids) < 2:
            raise ValueError("align_shapes requires at least two shapes")
        page = self._resolve_page(doc_name, page_name_or_index)
        shapes = [page.Shapes.ItemFromID(int(shape_id)) for shape_id in shape_ids]
        reference = page.Shapes.ItemFromID(reference_shape_id) if reference_shape_id else shapes[0]
        ref_x = reference.CellsU("PinX").ResultIU
        ref_y = reference.CellsU("PinY").ResultIU
        ref_w = reference.CellsU("Width").ResultIU
        ref_h = reference.CellsU("Height").ResultIU
        mode = str(alignment).lower().replace("-", "_")
        for shape in shapes:
            width = shape.CellsU("Width").ResultIU
            height = shape.CellsU("Height").ResultIU
            if mode == "left":
                shape.CellsU("PinX").ResultIU = ref_x - ref_w / 2 + width / 2
            elif mode in ("center", "horizontal_center"):
                shape.CellsU("PinX").ResultIU = ref_x
            elif mode == "right":
                shape.CellsU("PinX").ResultIU = ref_x + ref_w / 2 - width / 2
            elif mode == "top":
                shape.CellsU("PinY").ResultIU = ref_y + ref_h / 2 - height / 2
            elif mode in ("middle", "vertical_middle"):
                shape.CellsU("PinY").ResultIU = ref_y
            elif mode == "bottom":
                shape.CellsU("PinY").ResultIU = ref_y - ref_h / 2 + height / 2
            else:
                raise ValueError(f"Unknown alignment: {alignment}")
        return [self._shape_info(shape) for shape in shapes]

    def distribute_shapes(
        self, shape_ids: list[int], distribution: str,
        page_name_or_index=None, doc_name: str = "",
    ) -> list[dict]:
        """Distribute three or more shapes by centers or equal edge-to-edge spacing."""
        if len(shape_ids) < 3:
            raise ValueError("distribute_shapes requires at least three shapes")
        page = self._resolve_page(doc_name, page_name_or_index)
        shapes = [page.Shapes.ItemFromID(int(shape_id)) for shape_id in shape_ids]
        mode = str(distribution).lower().replace("-", "_")

        if mode in ("horizontal_center", "horizontal_space"):
            shapes.sort(key=lambda s: s.CellsU("PinX").ResultIU)
            first, last = shapes[0], shapes[-1]
            if mode == "horizontal_center":
                start = first.CellsU("PinX").ResultIU
                step = (last.CellsU("PinX").ResultIU - start) / (len(shapes) - 1)
                for index, shape in enumerate(shapes[1:-1], start=1):
                    shape.CellsU("PinX").ResultIU = start + step * index
            else:
                left = first.CellsU("PinX").ResultIU - first.CellsU("Width").ResultIU / 2
                right = last.CellsU("PinX").ResultIU + last.CellsU("Width").ResultIU / 2
                total_width = sum(shape.CellsU("Width").ResultIU for shape in shapes)
                gap = (right - left - total_width) / (len(shapes) - 1)
                cursor = left
                for shape in shapes:
                    width = shape.CellsU("Width").ResultIU
                    shape.CellsU("PinX").ResultIU = cursor + width / 2
                    cursor += width + gap
        elif mode in ("vertical_middle", "vertical_space"):
            shapes.sort(key=lambda s: s.CellsU("PinY").ResultIU)
            first, last = shapes[0], shapes[-1]
            if mode == "vertical_middle":
                start = first.CellsU("PinY").ResultIU
                step = (last.CellsU("PinY").ResultIU - start) / (len(shapes) - 1)
                for index, shape in enumerate(shapes[1:-1], start=1):
                    shape.CellsU("PinY").ResultIU = start + step * index
            else:
                bottom = first.CellsU("PinY").ResultIU - first.CellsU("Height").ResultIU / 2
                top = last.CellsU("PinY").ResultIU + last.CellsU("Height").ResultIU / 2
                total_height = sum(shape.CellsU("Height").ResultIU for shape in shapes)
                gap = (top - bottom - total_height) / (len(shapes) - 1)
                cursor = bottom
                for shape in shapes:
                    height = shape.CellsU("Height").ResultIU
                    shape.CellsU("PinY").ResultIU = cursor + height / 2
                    cursor += height + gap
        else:
            raise ValueError(f"Unknown distribution: {distribution}")
        return [self._shape_info(shape) for shape in shapes]

    def compact_layout_shapes(
        self, shape_ids: list[int], axis: str = "vertical", gap: float = 0.16,
        order: str = "auto", preserve_center: bool = True,
        page_name_or_index=None, doc_name: str = "",
    ) -> list[dict]:
        """Pack editable 2-D shapes with an exact edge-to-edge gap.

        Vertical auto order is top-to-bottom; horizontal auto order is left-to-right.
        The overall group center is preserved by default, so compacting does not cause
        the figure to drift across the page.
        """
        if len(shape_ids) < 2:
            raise ValueError("compact_layout_shapes requires at least two shapes")
        if gap < 0:
            raise ValueError("gap must be non-negative")
        page = self._resolve_page(doc_name, page_name_or_index)
        shapes = [page.Shapes.ItemFromID(int(shape_id)) for shape_id in shape_ids]
        if any(int(shape.OneD) != 0 for shape in shapes):
            raise ValueError("compact_layout_shapes accepts 2-D controls only, not connectors")

        mode = str(axis).lower().replace("-", "_")
        ordering = str(order).lower().replace("-", "_")
        if mode not in ("horizontal", "vertical"):
            raise ValueError("axis must be horizontal or vertical")
        if ordering not in ("auto", "given"):
            raise ValueError("order must be auto or given")

        if ordering == "auto":
            if mode == "horizontal":
                shapes.sort(key=lambda shape: shape.CellsU("PinX").ResultIU)
            else:
                shapes.sort(key=lambda shape: shape.CellsU("PinY").ResultIU, reverse=True)

        if mode == "horizontal":
            sizes = [shape.CellsU("Width").ResultIU for shape in shapes]
            left = min(shape.CellsU("PinX").ResultIU - shape.CellsU("Width").ResultIU / 2 for shape in shapes)
            right = max(shape.CellsU("PinX").ResultIU + shape.CellsU("Width").ResultIU / 2 for shape in shapes)
            center = (left + right) / 2 if preserve_center else left + (sum(sizes) + gap * (len(shapes) - 1)) / 2
            cursor = center - (sum(sizes) + gap * (len(shapes) - 1)) / 2
            for shape, size in zip(shapes, sizes):
                shape.CellsU("PinX").ResultIU = cursor + size / 2
                cursor += size + gap
        else:
            sizes = [shape.CellsU("Height").ResultIU for shape in shapes]
            bottom = min(shape.CellsU("PinY").ResultIU - shape.CellsU("Height").ResultIU / 2 for shape in shapes)
            top = max(shape.CellsU("PinY").ResultIU + shape.CellsU("Height").ResultIU / 2 for shape in shapes)
            center = (bottom + top) / 2 if preserve_center else top - (sum(sizes) + gap * (len(shapes) - 1)) / 2
            cursor = center + (sum(sizes) + gap * (len(shapes) - 1)) / 2
            for shape, size in zip(shapes, sizes):
                shape.CellsU("PinY").ResultIU = cursor - size / 2
                cursor -= size + gap
        return [self._shape_info(shape) for shape in shapes]

    def apply_scientific_style(
        self, shape_id: int, role: str = "neutral", profile: str = "sci_compact",
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Apply a semantic SCI style role to an existing editable shape."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(int(shape_id))
        definition = _scientific_defaults(
            {"type": "line" if int(shape.OneD) else "rectangle", "text": str(shape.Text), "semantic_role": role},
            profile, role,
        )
        format_keys = {
            "fill_color", "line_color", "line_weight", "font_size", "font_color",
            "transparency", "line_pattern", "begin_arrow", "end_arrow",
            "begin_arrow_size", "end_arrow_size", "line_transparency", "line_cap",
            "rounding", "route_style", "connector_appearance",
            "fill_background_color", "fill_pattern", "fill_background_transparency",
            "font_name", "bold", "italic", "underline", "h_align", "v_align",
            "text_margin_left", "text_margin_right", "text_margin_top", "text_margin_bottom",
            "text_background_color", "text_background_transparency", "line_spacing",
            "paragraph_before", "paragraph_after", "angle",
        }
        formatting = {key: value for key, value in definition.items() if key in format_keys}
        return self.set_shape_format(
            int(shape_id), page_name_or_index=page_name_or_index,
            doc_name=doc_name, **formatting,
        )

    def batch_update_shapes(
        self, updates: list[dict], page_name_or_index=None, doc_name: str = "",
    ) -> list[dict]:
        """Update text, position, size, rotation, and formatting for many shapes."""
        page = self._resolve_page(doc_name, page_name_or_index)
        format_keys = {
            "fill_color", "line_color", "line_weight", "font_size", "font_color",
            "transparency", "line_pattern", "begin_arrow", "end_arrow",
            "begin_arrow_size", "end_arrow_size", "line_transparency", "line_cap",
            "rounding", "route_style", "connector_appearance",
            "fill_background_color", "fill_pattern", "fill_background_transparency",
            "font_name", "bold", "italic", "underline", "h_align", "v_align",
            "text_margin_left", "text_margin_right", "text_margin_top",
            "text_margin_bottom", "text_background_color",
            "text_background_transparency", "line_spacing",
            "paragraph_before", "paragraph_after", "angle",
        }
        results: list[dict] = []
        for update in updates:
            shape_id = int(update["shape_id"])
            shape = page.Shapes.ItemFromID(shape_id)
            if "text" in update:
                shape.Text = update["text"]
            if "x" in update:
                shape.CellsU("PinX").ResultIU = update["x"]
            if "y" in update:
                shape.CellsU("PinY").ResultIU = update["y"]
            if "width" in update:
                shape.CellsU("Width").ResultIU = update["width"]
            if "height" in update:
                shape.CellsU("Height").ResultIU = update["height"]
            formatting = dict(update.get("format", {}))
            formatting.update({key: update[key] for key in format_keys if key in update})
            if formatting:
                self.set_shape_format(
                    shape_id, page_name_or_index=page_name_or_index,
                    doc_name=doc_name, **formatting,
                )
            results.append(self._shape_info(shape))
        return results

    @staticmethod
    def _segment_intersects_rect(
        p1: tuple[float, float], p2: tuple[float, float],
        rect: tuple[float, float, float, float],
    ) -> bool:
        """Liang-Barsky segment/rectangle intersection test."""
        x1, y1 = p1
        x2, y2 = p2
        left, bottom, right, top = rect
        dx, dy = x2 - x1, y2 - y1
        p = (-dx, dx, -dy, dy)
        q = (x1 - left, right - x1, y1 - bottom, top - y1)
        u1, u2 = 0.0, 1.0
        for pi, qi in zip(p, q):
            if abs(pi) < 1e-12:
                if qi < 0:
                    return False
                continue
            ratio = qi / pi
            if pi < 0:
                u1 = max(u1, ratio)
            else:
                u2 = min(u2, ratio)
            if u1 > u2:
                return False
        return True

    @staticmethod
    def _expanded_rect(
        rect: tuple[float, float, float, float], clearance: float,
    ) -> tuple[float, float, float, float]:
        left, bottom, right, top = rect
        return left - clearance, bottom - clearance, right + clearance, top + clearance

    @staticmethod
    def _point_in_rect(
        point: tuple[float, float], rect: tuple[float, float, float, float],
        tolerance: float = 0.01,
    ) -> bool:
        left, bottom, right, top = rect
        x, y = point
        return left - tolerance <= x <= right + tolerance and bottom - tolerance <= y <= top + tolerance

    def _shape_path_points(self, shape) -> list[tuple[float, float]]:
        """Read page-coordinate vertices from a native 1-D Visio shape."""
        try:
            stored = str(shape.CellsU("Prop.SafeRoutePoints.Value").ResultStr(""))
            parsed = []
            for pair in stored.split(";"):
                if not pair.strip():
                    continue
                x_text, y_text = pair.split(",", 1)
                parsed.append((float(x_text), float(y_text)))
            if len(parsed) >= 2:
                return parsed
        except Exception:
            pass
        begin = None
        end = None
        try:
            begin = (
                float(shape.CellsU("BeginX").ResultIU),
                float(shape.CellsU("BeginY").ResultIU),
            )
            end = (
                float(shape.CellsU("EndX").ResultIU),
                float(shape.CellsU("EndY").ResultIU),
            )
        except Exception:
            pass
        points: list[tuple[float, float]] = []
        try:
            pin_x = float(shape.CellsU("PinX").ResultIU)
            pin_y = float(shape.CellsU("PinY").ResultIU)
            loc_x = float(shape.CellsU("LocPinX").ResultIU)
            loc_y = float(shape.CellsU("LocPinY").ResultIU)
            angle = float(shape.CellsU("Angle").ResultIU)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            for section in range(10, 32):
                try:
                    if not shape.SectionExists(section, 0):
                        continue
                    rows = int(shape.RowCount(section))
                except Exception:
                    continue
                for row in range(1, rows):
                    try:
                        local_x = float(shape.CellsSRC(section, row, 0).ResultIU)
                        local_y = float(shape.CellsSRC(section, row, 1).ResultIU)
                    except Exception:
                        continue
                    rel_x, rel_y = local_x - loc_x, local_y - loc_y
                    points.append((
                        pin_x + rel_x * cos_a - rel_y * sin_a,
                        pin_y + rel_x * sin_a + rel_y * cos_a,
                    ))
        except Exception:
            points = []

        ordered: list[tuple[float, float]] = [begin] if begin is not None else []
        for point in points:
            if not ordered or abs(point[0] - ordered[-1][0]) > 1e-6 or abs(point[1] - ordered[-1][1]) > 1e-6:
                ordered.append(point)
        if end is not None and (not ordered or abs(end[0] - ordered[-1][0]) > 1e-6 or abs(end[1] - ordered[-1][1]) > 1e-6):
            ordered.append(end)
        if len(ordered) < 2:
            center = (
                float(shape.CellsU("PinX").ResultIU),
                float(shape.CellsU("PinY").ResultIU),
            )
            return [center, center]
        return ordered

    def draw_safe_orthogonal_connector(
        self, from_shape_id: int, to_shape_id: int,
        obstacle_ids: list[int] | None = None,
        preferred_axis: str = "auto", clearance: float = 0.12,
        role: str = "data_flow", profile: str = "sci_compact",
        enforce_clearance: bool = True,
        terminal_stub: float = 0.0,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Draw a compact obstacle-aware orthogonal arrow.

        This keeps native Visio arrowheads and avoids obstacles, but it no longer
        forces a visible terminal stub by default. The result is closer to Visio's
        natural publication-style routing and avoids the small hook-like segments
        that can look heavy in dense SCI figures.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        source = page.Shapes.ItemFromID(int(from_shape_id))
        target = page.Shapes.ItemFromID(int(to_shape_id))
        adjustment = None
        terminal_stub = max(float(terminal_stub), 0.0)
        if enforce_clearance:
            adjustment = self._ensure_connector_clearance(
                page, source, target,
                max(float(clearance), 0.08),
            )

        source_box = self._shape_bounds(source)
        target_box = self._shape_bounds(target)
        sx_center = (source_box[0] + source_box[2]) / 2
        sy_center = (source_box[1] + source_box[3]) / 2
        tx_center = (target_box[0] + target_box[2]) / 2
        ty_center = (target_box[1] + target_box[3]) / 2
        dx, dy = tx_center - sx_center, ty_center - sy_center
        axis = str(preferred_axis or "auto").lower().replace("-", "_")
        if axis == "auto":
            axis = "horizontal" if abs(dx) >= abs(dy) else "vertical"
        if axis not in ("horizontal", "vertical"):
            raise ValueError("preferred_axis must be auto, horizontal, or vertical")

        if axis == "horizontal":
            direction = 1.0 if dx >= 0 else -1.0
            start = (source_box[2] if direction > 0 else source_box[0], sy_center)
            finish = (target_box[0] if direction > 0 else target_box[2], ty_center)
            start_stub = (start[0] + direction * terminal_stub, start[1])
            finish_stub = (finish[0] - direction * terminal_stub, finish[1])
        else:
            direction = 1.0 if dy >= 0 else -1.0
            start = (sx_center, source_box[3] if direction > 0 else source_box[1])
            finish = (tx_center, target_box[1] if direction > 0 else target_box[3])
            start_stub = (start[0], start[1] + direction * terminal_stub)
            finish_stub = (finish[0], finish[1] - direction * terminal_stub)

        if obstacle_ids:
            obstacle_shapes = [page.Shapes.ItemFromID(int(shape_id)) for shape_id in obstacle_ids]
        else:
            obstacle_shapes = []
            for index in range(1, page.Shapes.Count + 1):
                candidate = page.Shapes.Item(index)
                if int(candidate.OneD) or int(candidate.ID) in (int(source.ID), int(target.ID)):
                    continue
                if self._get_semantic_role(candidate) == "container":
                    continue
                obstacle_shapes.append(candidate)
        obstacles = [self._expanded_rect(self._shape_bounds(shape), float(clearance)) for shape in obstacle_shapes]

        def collision_count(points: list[tuple[float, float]]) -> int:
            return sum(
                1
                for rect in obstacles
                if any(self._segment_intersects_rect(a, b, rect) for a, b in zip(points, points[1:]))
            )

        candidates: list[list[tuple[float, float]]] = []
        if axis == "horizontal":
            if abs(start[1] - finish[1]) <= 1e-6:
                candidates.append([start, finish])
            midpoint = (start[0] + finish[0]) / 2
            if terminal_stub:
                candidates.append([
                    start, start_stub, (midpoint, start[1]),
                    (midpoint, finish[1]), finish_stub, finish,
                ])
            else:
                candidates.append([start, (midpoint, start[1]), (midpoint, finish[1]), finish])
            above = max([rect[3] for rect in obstacles] + [start[1], finish[1]]) + clearance
            below = min([rect[1] for rect in obstacles] + [start[1], finish[1]]) - clearance
            if terminal_stub:
                candidates += [
                    [start, start_stub, (start_stub[0], above), (finish_stub[0], above), finish_stub, finish],
                    [start, start_stub, (start_stub[0], below), (finish_stub[0], below), finish_stub, finish],
                ]
            else:
                candidates += [
                    [start, (start[0], above), (finish[0], above), finish],
                    [start, (start[0], below), (finish[0], below), finish],
                ]
        else:
            if abs(start[0] - finish[0]) <= 1e-6:
                candidates.append([start, finish])
            midpoint = (start[1] + finish[1]) / 2
            if terminal_stub:
                candidates.append([
                    start, start_stub, (start[0], midpoint),
                    (finish[0], midpoint), finish_stub, finish,
                ])
            else:
                candidates.append([start, (start[0], midpoint), (finish[0], midpoint), finish])
            right = max([rect[2] for rect in obstacles] + [start[0], finish[0]]) + clearance
            left = min([rect[0] for rect in obstacles] + [start[0], finish[0]]) - clearance
            if terminal_stub:
                candidates += [
                    [start, start_stub, (right, start_stub[1]), (right, finish_stub[1]), finish_stub, finish],
                    [start, start_stub, (left, start_stub[1]), (left, finish_stub[1]), finish_stub, finish],
                ]
            else:
                candidates += [
                    [start, (right, start[1]), (right, finish[1]), finish],
                    [start, (left, start[1]), (left, finish[1]), finish],
                ]

        def clean_path(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
            cleaned: list[tuple[float, float]] = []
            for point in path:
                if not cleaned or math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) > 1e-6:
                    cleaned.append(point)
            return cleaned

        candidates = [clean_path(path) for path in candidates]

        def path_length(points: list[tuple[float, float]]) -> float:
            return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))

        points = min(candidates, key=lambda item: (collision_count(item), path_length(item)))
        remaining = collision_count(points)
        if remaining:
            raise ValueError(
                f"No collision-free orthogonal route found; {remaining} obstacle(s) "
                "intrude into the connector corridor. Increase the gap, move the "
                "obstacle, or pass a narrower obstacle_ids list."
            )
        flat = [coordinate for point in points for coordinate in point]
        connector = page.DrawPolyline(flat, 0)
        style = _scientific_defaults(
            {"type": "polyline", "semantic_role": role}, profile, role,
        )
        _apply_line_format(
            connector, style.get("line_color", ""), style.get("line_weight", ""),
            style.get("line_pattern", ""), style.get("begin_arrow", ""),
            style.get("end_arrow", "standard"), style.get("begin_arrow_size", ""),
            style.get("end_arrow_size", "2"), style.get("line_transparency", ""),
            style.get("line_cap", ""), style.get("rounding", ""),
            style.get("route_style", ""), style.get("connector_appearance", ""),
        )
        self._set_semantic_role(connector, role)
        self._set_shape_data_text(
            connector, "SafeRoutePoints", "SafeRoutePoints",
            ";".join(f"{x:.6f},{y:.6f}" for x, y in points),
        )
        self._set_shape_data_text(connector, "SafeRouteFrom", "SafeRouteFrom", str(int(source.ID)))
        self._set_shape_data_text(connector, "SafeRouteTo", "SafeRouteTo", str(int(target.ID)))
        if terminal_stub:
            self._set_shape_data_text(connector, "TerminalStub", "TerminalStub", f"{terminal_stub:.6f}")
        info = self._shape_info(connector)
        info["route_points"] = [[round(x, 4), round(y, 4)] for x, y in points]
        if adjustment:
            info["layout_adjustment"] = adjustment
        return info

    def audit_scientific_layout(
        self, min_control_gap: float = 0.14, connector_clearance: float = 0.04,
        min_connector_length: float = 0.12,
        terminal_stub: float = 0.0, corner_exclusion: float = 0.10,
        terminal_tolerance: float = 0.02,
        audit_terminal_geometry: bool = False,
        page_name_or_index=None, doc_name: str = "",
    ) -> dict:
        """Audit spacing and connector crossings for compact scientific figures."""
        page = self._resolve_page(doc_name, page_name_or_index)
        controls: list[dict] = []
        connectors: list[object] = []
        for index in range(1, page.Shapes.Count + 1):
            shape = page.Shapes.Item(index)
            role = self._get_semantic_role(shape)
            if int(shape.OneD) or role in ("data_flow", "decision_flow"):
                connectors.append(shape)
            elif role != "container":
                controls.append({
                    "shape": shape, "shape_id": int(shape.ID), "name": shape.Name,
                    "role": role or "unclassified", "text": str(shape.Text),
                    "bounds": self._shape_bounds(shape),
                })

        issues: list[dict] = []
        non_text = [item for item in controls if item["role"] != "text"]
        for index, first in enumerate(non_text):
            fl, fb, fr, ft = first["bounds"]
            for second in non_text[index + 1:]:
                sl, sb, sr, st = second["bounds"]
                overlap_x = min(fr, sr) - max(fl, sl)
                overlap_y = min(ft, st) - max(fb, sb)
                if overlap_x > 0.005 and overlap_y > 0.005:
                    issues.append({
                        "severity": "error", "type": "control_overlap",
                        "shape_ids": [first["shape_id"], second["shape_id"]],
                        "message": "Two controls overlap; move or resize them before export.",
                    })
                    continue
                if overlap_y > 0:
                    gap = max(sl - fr, fl - sr)
                elif overlap_x > 0:
                    gap = max(sb - ft, fb - st)
                else:
                    continue
                if 0 <= gap < min_control_gap:
                    issues.append({
                        "severity": "warning", "type": "control_gap_too_small",
                        "shape_ids": [first["shape_id"], second["shape_id"]],
                        "measured_gap": round(gap, 4), "required_gap": min_control_gap,
                        "message": "Control gap is too small for a visible native arrowhead.",
                    })

        endpoint_map: dict[int, set[int]] = {}
        terminal_map: dict[int, dict[str, int]] = {}
        for index in range(1, page.Connects.Count + 1):
            try:
                connection = page.Connects.Item(index)
                connector_id = int(connection.FromSheet.ID)
                target_id = int(connection.ToSheet.ID)
                endpoint_map.setdefault(connector_id, set()).add(target_id)
                from_cell = str(connection.FromCell.Name).lower()
                if "begin" in from_cell:
                    terminal_map.setdefault(connector_id, {})["begin"] = target_id
                elif "end" in from_cell:
                    terminal_map.setdefault(connector_id, {})["end"] = target_id
            except Exception:
                continue

        def stored_shape_id(shape, row_name: str) -> int | None:
            try:
                return int(float(shape.CellsU(f"Prop.{row_name}.Value").ResultStr("")))
            except Exception:
                return None

        def terminal_issue(
            connector_id: int, terminal_name: str, endpoint: tuple[float, float],
            neighbor: tuple[float, float], control_id: int,
        ) -> list[dict]:
            try:
                control_shape = page.Shapes.ItemFromID(int(control_id))
            except Exception:
                return []
            left, bottom, right, top = self._shape_bounds(control_shape)
            x, y = endpoint
            distances = {
                "left": abs(x - left), "right": abs(x - right),
                "bottom": abs(y - bottom), "top": abs(y - top),
            }
            side = min(distances, key=distances.get)
            vx, vy = neighbor[0] - x, neighbor[1] - y
            segment_length = math.hypot(vx, vy)
            horizontal_side = side in ("left", "right")
            perpendicular = (
                abs(vy) <= terminal_tolerance and abs(vx) > terminal_tolerance
                if horizontal_side else
                abs(vx) <= terminal_tolerance and abs(vy) > terminal_tolerance
            )
            along = y if horizontal_side else x
            low, high = (bottom, top) if horizontal_side else (left, right)
            results: list[dict] = []
            if min(along - low, high - along) < corner_exclusion:
                results.append({
                    "severity": "error", "type": "connector_attaches_near_corner",
                    "connector_id": connector_id, "shape_id": control_id,
                    "terminal": terminal_name, "side": side,
                    "required_corner_exclusion": corner_exclusion,
                    "message": "Connector attaches inside the rounded-corner exclusion zone; use the side-center region.",
                })
            if not perpendicular:
                results.append({
                    "severity": "error", "type": "connector_terminal_not_perpendicular",
                    "connector_id": connector_id, "shape_id": control_id,
                    "terminal": terminal_name, "side": side,
                    "message": "The first/last connector segment must be perpendicular to the attached shape side.",
                })
            if segment_length + terminal_tolerance < terminal_stub:
                results.append({
                    "severity": "error", "type": "connector_terminal_stub_too_short",
                    "connector_id": connector_id, "shape_id": control_id,
                    "terminal": terminal_name, "measured_length": round(segment_length, 4),
                    "required_length": terminal_stub,
                    "message": "Connector turns too close to the control; extend its straight terminal stub.",
                })
            return results

        for connector in connectors:
            points = self._shape_path_points(connector)
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
            if length < min_connector_length:
                issues.append({
                    "severity": "error", "type": "connector_too_short",
                    "shape_id": int(connector.ID), "measured_length": round(length, 4),
                    "required_length": min_connector_length,
                    "message": "Connector is too short; its arrowhead can overlap the target control.",
                })
            connector_id = int(connector.ID)
            terminals = dict(terminal_map.get(connector_id, {}))
            terminals.setdefault("begin", stored_shape_id(connector, "SafeRouteFrom"))
            terminals.setdefault("end", stored_shape_id(connector, "SafeRouteTo"))
            if audit_terminal_geometry and len(points) >= 2:
                if terminals.get("begin") is not None:
                    issues.extend(terminal_issue(
                        connector_id, "begin", points[0], points[1], terminals["begin"],
                    ))
                if terminals.get("end") is not None:
                    issues.extend(terminal_issue(
                        connector_id, "end", points[-1], points[-2], terminals["end"],
                    ))
            endpoints = endpoint_map.get(connector_id, set()) | {
                value for value in terminals.values() if value is not None
            }
            for control in controls:
                if control["shape_id"] in endpoints:
                    continue
                if self._point_in_rect(points[0], control["bounds"]) or self._point_in_rect(points[-1], control["bounds"]):
                    continue
                clearance = connector_clearance if control["role"] != "text" else max(connector_clearance, 0.06)
                rect = self._expanded_rect(control["bounds"], clearance)
                if any(self._segment_intersects_rect(a, b, rect) for a, b in zip(points, points[1:])):
                    issues.append({
                        "severity": "error", "type": "connector_crosses_shape",
                        "connector_id": int(connector.ID), "shape_id": control["shape_id"],
                        "shape_role": control["role"],
                        "message": "Connector crosses or crowds a control/text box; reroute it before export.",
                    })

        errors = sum(issue["severity"] == "error" for issue in issues)
        warnings = sum(issue["severity"] == "warning" for issue in issues)
        return {
            "status": "pass" if not errors and not warnings else ("error" if errors else "warning"),
            "errors": errors, "warnings": warnings, "issue_count": len(issues),
            "issues": issues,
            "rules": {
                "min_control_gap": min_control_gap,
                "connector_clearance": connector_clearance,
                "min_connector_length": min_connector_length,
                "terminal_stub": terminal_stub,
                "corner_exclusion": corner_exclusion,
                "terminal_tolerance": terminal_tolerance,
                "audit_terminal_geometry": audit_terminal_geometry,
            },
        }

    def delete_shape(
        self,
        shape_id: int,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Delete a shape by ID."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        name = shape.Name
        shape.Delete()
        return {"deleted": name, "shape_id": shape_id}

    def group_shapes(
        self,
        shape_ids: list[int],
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Group multiple shapes together."""
        page = self._resolve_page(doc_name, page_name_or_index)
        # Select shapes
        window = self.app.ActiveWindow
        window.DeselectAll()
        for sid in shape_ids:
            shape = page.Shapes.ItemFromID(sid)
            window.Select(shape, 2)  # visSelect
        selection = window.Selection
        group = selection.Group()
        return self._shape_info(group)

    # ── Batch Operations ──────────────────────────────────────────────

    @staticmethod
    def _shape_bounds(shape) -> tuple[float, float, float, float]:
        """Return left, bottom, right, top bounds in page inches."""
        pin_x = float(shape.CellsU("PinX").ResultIU)
        pin_y = float(shape.CellsU("PinY").ResultIU)
        width = float(shape.CellsU("Width").ResultIU)
        height = float(shape.CellsU("Height").ResultIU)
        return pin_x - width / 2, pin_y - height / 2, pin_x + width / 2, pin_y + height / 2

    @staticmethod
    def _set_semantic_role(shape, role: str) -> None:
        """Store a semantic role as Shape Data so audits survive save/reopen."""
        if not role:
            return
        try:
            if not shape.SectionExists(visSectionProp, 0):
                shape.AddSection(visSectionProp)
            try:
                shape.AddNamedRow(visSectionProp, "SemanticRole", 0)
            except Exception:
                pass
            escaped = str(role).replace('"', '""')
            shape.CellsU("Prop.SemanticRole.Label").FormulaU = '"SemanticRole"'
            shape.CellsU("Prop.SemanticRole.Value").FormulaU = f'"{escaped}"'
        except Exception:
            logger.debug("Unable to attach SemanticRole Shape Data", exc_info=True)

    @staticmethod
    def _get_semantic_role(shape) -> str:
        try:
            return str(shape.CellsU("Prop.SemanticRole.Value").ResultStr("")).strip().lower()
        except Exception:
            return ""

    @staticmethod
    def _set_shape_data_text(shape, row_name: str, label: str, value: str) -> None:
        try:
            if not shape.SectionExists(visSectionProp, 0):
                shape.AddSection(visSectionProp)
            try:
                shape.AddNamedRow(visSectionProp, row_name, 0)
            except Exception:
                pass
            escaped_label = str(label).replace('"', '""')
            escaped_value = str(value).replace('"', '""')
            shape.CellsU(f"Prop.{row_name}.Label").FormulaU = f'"{escaped_label}"'
            shape.CellsU(f"Prop.{row_name}.Value").FormulaU = f'"{escaped_value}"'
        except Exception:
            logger.debug("Unable to attach Shape Data row %s", row_name, exc_info=True)

    def _ensure_connector_clearance(
        self, page, from_shape, to_shape, minimum: float,
    ) -> dict | None:
        """Move the target just enough to expose a native arrowhead between controls."""
        if minimum <= 0 or int(from_shape.OneD) or int(to_shape.OneD):
            return None
        fx = float(from_shape.CellsU("PinX").ResultIU)
        fy = float(from_shape.CellsU("PinY").ResultIU)
        tx = float(to_shape.CellsU("PinX").ResultIU)
        ty = float(to_shape.CellsU("PinY").ResultIU)
        fw = float(from_shape.CellsU("Width").ResultIU)
        fh = float(from_shape.CellsU("Height").ResultIU)
        tw = float(to_shape.CellsU("Width").ResultIU)
        th = float(to_shape.CellsU("Height").ResultIU)
        dx, dy = tx - fx, ty - fy

        if abs(dx) >= abs(dy):
            direction = 1.0 if dx >= 0 else -1.0
            gap = abs(dx) - (fw + tw) / 2
            if gap >= minimum:
                return None
            delta = minimum - gap
            to_shape.CellsU("PinX").ResultIU = tx + direction * delta
            return {
                "axis": "horizontal", "old_gap": round(gap, 4),
                "new_gap": round(minimum, 4), "moved_shape_id": int(to_shape.ID),
                "delta": round(direction * delta, 4),
            }

        direction = 1.0 if dy >= 0 else -1.0
        gap = abs(dy) - (fh + th) / 2
        if gap >= minimum:
            return None
        delta = minimum - gap
        to_shape.CellsU("PinY").ResultIU = ty + direction * delta
        return {
            "axis": "vertical", "old_gap": round(gap, 4),
            "new_gap": round(minimum, 4), "moved_shape_id": int(to_shape.ID),
            "delta": round(direction * delta, 4),
        }

    def batch_draw_shapes(
        self,
        shapes: list[dict],
        page_name_or_index=None,
        doc_name: str = "",
        style_profile: str = "sci_compact",
        default_role: str = "neutral",
    ) -> dict:
        """Create multiple shapes in one call.

        Each item in *shapes* is a dict with keys:
            id          – local ref string (used later for connections)
            type        – "drop" | "rectangle" | "oval" | "line"
            For "drop": master_name, stencil_name, x, y
            For "rectangle"/"oval": x1, y1, x2, y2
            For "line": x1, y1, x2, y2
            Optional: text, fill_color, line_color, line_weight,
                      font_size, font_color, transparency,
                      width, height

        Returns:
            {"ref_map": {ref_id: shape_id, ...}, "shapes": [shape_info, ...]}
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        ref_map: dict[str, int] = {}
        results: list[dict] = []
        stencil_cache: dict[str, object] = {}

        for raw_defn in shapes:
            defn = _scientific_defaults(raw_defn, style_profile, default_role)
            shape = None
            stype = defn.get("type", "drop")

            if stype == "drop":
                stencil_name = defn["stencil_name"]
                if stencil_name not in stencil_cache:
                    stencil_cache[stencil_name] = self._open_stencil(stencil_name)
                stencil = stencil_cache[stencil_name]
                master = stencil.Masters.ItemU(defn["master_name"])
                shape = page.Drop(master, defn["x"], defn["y"])
            elif stype == "rectangle":
                shape = page.DrawRectangle(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"]
                )
            elif stype == "rounded_rectangle":
                shape = page.DrawRectangle(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"]
                )
                defn.setdefault("rounding", "0.08 in")
            elif stype == "text_box":
                shape = page.DrawRectangle(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"]
                )
                if not defn.get("fill_color") and not defn.get("fill_pattern"):
                    shape.CellsU("FillPattern").FormulaU = "0"
                if not defn.get("line_color") and not defn.get("line_pattern"):
                    shape.CellsU("LinePattern").FormulaU = "0"
            elif stype == "oval":
                shape = page.DrawOval(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"]
                )
            elif stype == "line":
                shape = page.DrawLine(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"]
                )
            elif stype == "polyline":
                shape = page.DrawPolyline(
                    defn["points"], defn.get("flags", 0)
                )
            elif stype == "bezier":
                shape = page.DrawBezier(
                    defn["points"], defn.get("degree", 3), defn.get("flags", 0)
                )
            elif stype == "quarter_arc":
                shape = page.DrawQuarterArc(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"],
                    defn.get("sweep", 0),
                )
            elif stype == "arc":
                shape = page.DrawArcByThreePoints(
                    defn["x1"], defn["y1"], defn["x2"], defn["y2"],
                    defn["control_x"], defn["control_y"],
                )
            elif stype == "regular_polygon":
                sides = int(defn["sides"])
                if sides < 3:
                    raise ValueError("regular_polygon sides must be at least 3")
                cx, cy, radius = defn["center_x"], defn["center_y"], defn["radius"]
                start = math.radians(float(defn.get("rotation", 0.0)))
                points: list[float] = []
                for index in range(sides):
                    angle = start + (2 * math.pi * index / sides)
                    points.extend([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
                points.extend(points[:2])
                shape = page.DrawPolyline(points, 1)
            elif stype == "diamond":
                spec = get_scientific_style_profile(style_profile or "sci_compact")
                cx, cy = defn["center_x"], defn["center_y"]
                width = float(defn.get("width", spec["geometry"]["diamond_width"]))
                height = float(defn.get("height", spec["geometry"]["diamond_height"]))
                if width <= 0 or height <= 0:
                    raise ValueError("diamond width and height must be positive")
                half_w, half_h = width / 2, height / 2
                points = [
                    cx - half_w, cy, cx, cy + half_h,
                    cx + half_w, cy, cx, cy - half_h,
                    cx - half_w, cy,
                ]
                shape = page.DrawPolyline(points, 1)
            elif stype == "spline":
                shape = page.DrawSpline(
                    defn["points"], defn.get("tolerance", 0.25),
                    defn.get("flags", 0),
                )
            elif stype == "nurbs":
                cp = defn["control_points"]
                num_cp = len(cp) // 2
                weights = defn.get("weights") or [1.0] * num_cp
                shape = page.DrawNURBS(
                    defn.get("degree", 3), 0, cp,
                    defn["knots"], weights,
                )
            else:
                raise ValueError(f"Unknown shape type: {stype}")

            # Optional text
            if defn.get("text"):
                shape.Text = defn["text"]

            # Optional resize
            if defn.get("width") is not None:
                shape.CellsU("Width").ResultIU = defn["width"]
            if defn.get("height") is not None:
                shape.CellsU("Height").ResultIU = defn["height"]

            # Optional formatting
            fmt_map = {
                "fill_color": "FillForegnd",
                "font_size": "Char.Size",
                "font_color": "Char.Color",
                "transparency": "FillForegndTrans",
            }
            for key, cell in fmt_map.items():
                val = defn.get(key)
                if val:
                    shape.CellsU(cell).FormulaU = val

            _apply_line_format(
                shape,
                defn.get("line_color", ""),
                defn.get("line_weight", ""),
                defn.get("line_pattern", ""),
                defn.get("begin_arrow", ""),
                defn.get("end_arrow", ""),
                defn.get("begin_arrow_size", ""),
                defn.get("end_arrow_size", ""),
                defn.get("line_transparency", ""),
                defn.get("line_cap", ""),
                defn.get("rounding", ""),
                defn.get("route_style", ""),
                defn.get("connector_appearance", ""),
            )
            _apply_fill_format(
                shape,
                defn.get("fill_color", ""),
                defn.get("fill_background_color", ""),
                defn.get("fill_pattern", ""),
                defn.get("transparency", ""),
                defn.get("fill_background_transparency", ""),
            )
            _apply_text_format(
                shape,
                defn.get("font_name", ""),
                defn.get("font_size", ""),
                defn.get("font_color", ""),
                defn.get("bold"),
                defn.get("italic"),
                defn.get("underline"),
                defn.get("h_align", ""),
                defn.get("v_align", ""),
                defn.get("text_margin_left", ""),
                defn.get("text_margin_right", ""),
                defn.get("text_margin_top", ""),
                defn.get("text_margin_bottom", ""),
                defn.get("text_background_color", ""),
                defn.get("text_background_transparency", ""),
                defn.get("line_spacing", ""),
                defn.get("paragraph_before", ""),
                defn.get("paragraph_after", ""),
            )
            angle_formula = _angle_formula(defn.get("angle", ""))
            if angle_formula:
                shape.CellsU("Angle").FormulaU = angle_formula

            semantic_role = defn.get("semantic_role", "")
            if not semantic_role and stype == "text_box":
                semantic_role = "text"
            self._set_semantic_role(shape, semantic_role)

            # Track ref
            ref_id = defn.get("id", str(shape.ID))
            ref_map[ref_id] = shape.ID
            results.append(self._shape_info(shape))

        return {"ref_map": ref_map, "shapes": results}

    def batch_connect_shapes(
        self,
        connections: list[dict],
        ref_map: dict[str, int] | None = None,
        page_name_or_index=None,
        doc_name: str = "",
        style_profile: str = "sci_compact",
        default_role: str = "data_flow",
        enforce_clearance: bool = True,
        min_clearance: float = 0.14,
        enforce_perpendicular: bool = True,
        terminal_stub: float = 0.0,
    ) -> list[dict]:
        """Connect multiple shape pairs in one call.

        Each item in *connections* is a dict:
            from              – ref ID string (looked up in ref_map) or int shape ID
            to                – ref ID string or int shape ID
            connector_master  – (optional) connector master name from stencil
            connector_stencil – (optional) stencil file for the connector
            from_port         – (optional) connection point row index on source shape
            to_port           – (optional) connection point row index on target shape

        When connector_master is provided, the connector is dropped from the stencil
        and glued to the shapes. Otherwise AutoConnect is used.

        When from_port / to_port are provided (>= 0), the connector glues to the
        specified connection point (CellsSRC section 7) instead of PinX. This is
        essential for sequence diagrams where messages must attach to specific
        points along the lifeline.

        Returns:
            list of connector shape info dicts.
        """
        page = self._resolve_page(doc_name, page_name_or_index)
        ref_map = ref_map or {}
        results: list[dict] = []
        stencil_cache: dict[str, object] = {}

        for raw_conn in connections:
            conn = _scientific_defaults(
                {"type": "line", **raw_conn}, style_profile, default_role,
            )
            from_id = self._resolve_ref(conn["from"], ref_map)
            to_id = self._resolve_ref(conn["to"], ref_map)
            from_shape = page.Shapes.ItemFromID(from_id)
            to_shape = page.Shapes.ItemFromID(to_id)

            connector_master = conn.get("connector_master", "")
            connector_stencil = conn.get("connector_stencil", "")
            adjustment = None
            if enforce_clearance and not connector_master:
                adjustment = self._ensure_connector_clearance(page, from_shape, to_shape, float(min_clearance))

            if enforce_perpendicular and not connector_master:
                from_box = self._shape_bounds(from_shape)
                to_box = self._shape_bounds(to_shape)
                dx = (to_box[0] + to_box[2] - from_box[0] - from_box[2]) / 2
                dy = (to_box[1] + to_box[3] - from_box[1] - from_box[3]) / 2
                aligned = abs(dy) <= 0.02 if abs(dx) >= abs(dy) else abs(dx) <= 0.02
                if not aligned:
                    conn["route_style"] = "right_angle"
                    conn["connector_appearance"] = "default"

            if connector_master and connector_stencil:
                # Use stencil connector for correct semantics
                if connector_stencil not in stencil_cache:
                    stencil_cache[connector_stencil] = self._open_stencil(connector_stencil)
                stencil = stencil_cache[connector_stencil]
                master = stencil.Masters.ItemU(connector_master)
                connector = page.Drop(master, 0, 0)
                # visSectionConnectionPts = 7
                from_port = conn.get("from_port", -1)
                to_port = conn.get("to_port", -1)
                if from_port is not None and from_port >= 0:
                    connector.CellsU("BeginX").GlueTo(from_shape.CellsSRC(7, from_port, 0))
                else:
                    connector.CellsU("BeginX").GlueTo(from_shape.CellsU("PinX"))
                if to_port is not None and to_port >= 0:
                    connector.CellsU("EndX").GlueTo(to_shape.CellsSRC(7, to_port, 0))
                else:
                    connector.CellsU("EndX").GlueTo(to_shape.CellsU("PinX"))
            else:
                # Fallback to AutoConnect
                from_shape.AutoConnect(to_shape, visAutoConnectDirNone)
                connector = page.Shapes.Item(page.Shapes.Count)

            # Optional: set text on connector
            if conn.get("text"):
                connector.Text = conn["text"]

            _apply_line_format(
                connector,
                conn.get("line_color", ""),
                conn.get("line_weight", ""),
                conn.get("line_pattern", ""),
                conn.get("begin_arrow", ""),
                conn.get("end_arrow", ""),
                conn.get("begin_arrow_size", ""),
                conn.get("end_arrow_size", ""),
                conn.get("line_transparency", ""),
                conn.get("line_cap", ""),
                conn.get("rounding", ""),
                conn.get("route_style", ""),
                conn.get("connector_appearance", ""),
            )
            self._set_semantic_role(
                connector, conn.get("semantic_role") or default_role,
            )
            info = self._shape_info(connector)
            if adjustment:
                info["layout_adjustment"] = adjustment
            results.append(info)

        return results

    @staticmethod
    def _resolve_ref(ref, ref_map: dict[str, int]) -> int:
        """Resolve a ref ID (string or int) to a Visio shape ID."""
        if isinstance(ref, int):
            return ref
        if isinstance(ref, str) and ref.isdigit():
            return int(ref)
        return ref_map[ref]

    # ── Read / Analysis ──────────────────────────────────────────────

    def list_shapes(
        self, page_name_or_index=None, doc_name: str = ""
    ) -> list[dict]:
        """List all shapes on a page."""
        page = self._resolve_page(doc_name, page_name_or_index)
        result = []
        for i in range(1, page.Shapes.Count + 1):
            shape = page.Shapes.Item(i)
            result.append(self._shape_info(shape))
        return result

    def get_shape_info(
        self,
        shape_id: int,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Get detailed info about a shape."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        info = self._shape_info(shape)
        # Add extra detail
        try:
            info["fill_color"] = shape.CellsU("FillForegnd").FormulaU
        except Exception:
            pass
        try:
            info["line_color"] = shape.CellsU("LineColor").FormulaU
        except Exception:
            pass
        try:
            info["line_weight"] = shape.CellsU("LineWeight").FormulaU
        except Exception:
            pass
        return info

    def get_connections(
        self, page_name_or_index=None, doc_name: str = ""
    ) -> list[dict]:
        """Get all connections (connects) on a page."""
        page = self._resolve_page(doc_name, page_name_or_index)
        result = []
        connects = page.Connects
        i = 1
        while True:
            try:
                conn = connects.Item(i)
                result.append({
                    "from_shape": conn.FromSheet.Name,
                    "from_shape_id": conn.FromSheet.ID,
                    "to_shape": conn.ToSheet.Name,
                    "to_shape_id": conn.ToSheet.ID,
                    "from_cell": conn.FromCell.Name,
                    "to_cell": conn.ToCell.Name,
                })
                i += 1
            except Exception:
                break
        return result

    def get_page_summary(
        self, page_name_or_index=None, doc_name: str = ""
    ) -> dict:
        """Get a summary of the page: shapes count, connections, etc."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shapes_count = page.Shapes.Count
        connections = self.get_connections(page_name_or_index, doc_name)
        return {
            "page_name": page.Name,
            "page_index": page.Index,
            "shapes_count": shapes_count,
            "connections_count": len(connections),
            "connections": connections,
        }

    def read_shape_data(
        self,
        shape_id: int,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Read custom Shape Data (properties) from a shape."""
        page = self._resolve_page(doc_name, page_name_or_index)
        shape = page.Shapes.ItemFromID(shape_id)
        data = {}
        try:
            section = shape.Section(visSectionProp)
            for r in range(shape.RowCount(visSectionProp)):
                row = section.Row(r)
                label = row.Cell(0).FormulaU  # Label
                value = row.Cell(1).FormulaU  # Value
                data[label] = value
        except Exception:
            pass
        return {"shape_id": shape_id, "shape_name": shape.Name, "data": data}

    # ── Stencils / Masters ───────────────────────────────────────────

    def list_stencils(self) -> list[dict]:
        """List all currently open stencils."""
        result = []
        for i in range(1, self.app.Documents.Count + 1):
            doc = self.app.Documents.Item(i)
            if doc.Type == 2:  # Stencil
                result.append({
                    "name": doc.Name,
                    "full_name": doc.FullName,
                    "masters_count": doc.Masters.Count,
                })
        return result

    def open_stencil(self, stencil_path: str) -> dict:
        """Open a stencil file."""
        stencil = self._open_stencil(stencil_path)
        return {
            "name": stencil.Name,
            "full_name": stencil.FullName,
            "masters_count": stencil.Masters.Count,
        }

    def list_masters(self, stencil_name: str) -> list[dict]:
        """List all masters in a stencil."""
        stencil = self._find_stencil(stencil_name)
        if stencil is None:
            stencil = self._open_stencil(stencil_name)
        result = []
        for i in range(1, stencil.Masters.Count + 1):
            master = stencil.Masters.Item(i)
            result.append({
                "name": master.Name,
                "name_u": master.NameU,
                "index": i,
            })
        return result

    # ── Export ────────────────────────────────────────────────────────

    def export_page_as_image(
        self,
        output_path: str,
        page_name_or_index=None,
        doc_name: str = "",
    ) -> dict:
        """Export a page as an image (PNG, SVG, etc. based on extension)."""
        page = self._resolve_page(doc_name, page_name_or_index)
        page.Export(output_path)
        return {"exported": output_path, "page": page.Name}

    # ── Internal Helpers ─────────────────────────────────────────────

    def _get_document(self, doc_name: str = ""):
        """Get document by name or the active document."""
        if doc_name:
            return self.app.Documents.Item(doc_name)
        return self.app.ActiveDocument

    def _get_page(self, doc, page_name_or_index):
        """Get page by name or 1-based index."""
        if page_name_or_index is None:
            return self.app.ActivePage
        if isinstance(page_name_or_index, int):
            return doc.Pages.Item(page_name_or_index)
        return doc.Pages.Item(page_name_or_index)

    def _resolve_page(self, doc_name: str = "", page_name_or_index=None):
        """Resolve to a Page object."""
        doc = self._get_document(doc_name)
        if page_name_or_index is not None:
            return self._get_page(doc, page_name_or_index)
        return self.app.ActivePage

    def _open_stencil(self, stencil_name: str):
        """Open a stencil if not already open. Accepts filename or full path."""
        existing = self._find_stencil(stencil_name)
        if existing:
            return existing
        # Open read-only + minimized
        return self.app.Documents.OpenEx(
            stencil_name, visOpenRO + visOpenMinimized
        )

    def _find_stencil(self, stencil_name: str):
        """Find an already open stencil by name."""
        for i in range(1, self.app.Documents.Count + 1):
            doc = self.app.Documents.Item(i)
            if doc.Type == 2:  # Stencil
                if (
                    doc.Name.lower() == stencil_name.lower()
                    or doc.FullName.lower() == stencil_name.lower()
                ):
                    return doc
        return None

    def _shape_info(self, shape) -> dict:
        """Extract basic info from a Shape object."""
        info = {
            "shape_id": shape.ID,
            "name": shape.Name,
            "text": shape.Text,
        }
        try:
            info["pin_x"] = round(shape.CellsU("PinX").ResultIU, 4)
            info["pin_y"] = round(shape.CellsU("PinY").ResultIU, 4)
            info["width"] = round(shape.CellsU("Width").ResultIU, 4)
            info["height"] = round(shape.CellsU("Height").ResultIU, 4)
        except Exception:
            pass
        return info
