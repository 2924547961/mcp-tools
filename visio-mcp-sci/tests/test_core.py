import unittest

from visio_mcp.visio_app import (
    VisioApp,
    _line_spacing_formula,
    _scientific_defaults,
    get_scientific_style_profile,
)


class ScientificProfileTests(unittest.TestCase):
    def test_compact_geometry_rules(self):
        profile = get_scientific_style_profile("sci_compact")
        geometry = profile["geometry"]
        self.assertEqual(geometry["diamond_width"], 1.20)
        self.assertEqual(geometry["diamond_height"], 0.54)
        self.assertGreaterEqual(geometry["min_control_gap"], 0.14)
        self.assertEqual(geometry["terminal_stub"], 0.0)
        self.assertEqual(geometry["corner_exclusion"], 0.10)

    def test_connector_geometry_rules_are_published(self):
        profile = get_scientific_style_profile("sci_compact")
        rules = " ".join(profile["aesthetic_rules"]).lower()
        self.assertIn("native visio connectors", rules)
        self.assertIn("side-normal terminal stubs", rules)
        self.assertIn("terminal stub", rules)

    def test_publication_palette_profiles_are_available(self):
        for name in ("sci_compact", "sci_nature", "sci_ieee", "sci_cell", "sci_mono"):
            profile = get_scientific_style_profile(name)
            self.assertIn("backbone", profile["roles"])
            self.assertIn("decision_flow", profile["roles"])
            self.assertTrue(profile["roles"]["backbone"]["fill_color"].startswith("RGB("))

    def test_multiline_defaults(self):
        result = _scientific_defaults(
            {"type": "rounded_rectangle", "text": "Line 1\nLine 2"},
            "sci_compact",
            "highlight",
        )
        self.assertEqual(result["font_size"], "10 pt")
        self.assertEqual(result["line_spacing"], "115%")

    def test_visio_relative_line_spacing(self):
        self.assertEqual(_line_spacing_formula("115%"), "-115%")
        self.assertEqual(_line_spacing_formula(-120), "-120%")
        self.assertEqual(_line_spacing_formula(0), "0")


class GeometryTests(unittest.TestCase):
    def test_segment_rectangle_intersection(self):
        rect = (1.0, 1.0, 2.0, 2.0)
        self.assertTrue(VisioApp._segment_intersects_rect((0.0, 1.5), (3.0, 1.5), rect))
        self.assertFalse(VisioApp._segment_intersects_rect((0.0, 0.0), (0.5, 0.5), rect))

    def test_expanded_rectangle(self):
        self.assertEqual(
            VisioApp._expanded_rect((1.0, 1.0, 2.0, 2.0), 0.1),
            (0.9, 0.9, 2.1, 2.1),
        )


if __name__ == "__main__":
    unittest.main()
