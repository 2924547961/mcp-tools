"""Regression test for compact SCI connector clearance and obstacle audits."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


PYTHON = sys.executable
ROOT = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.mkdtemp(prefix="visio-mcp-sci-"))


async def main() -> None:
    params = StdioServerParameters(command=PYTHON, args=["-m", "visio_mcp"])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()

            async def call(name: str, args: dict) -> object:
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(f"{name}: {result.content}")
                for block in result.content:
                    value = getattr(block, "text", None)
                    if value:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict) and "error" in parsed:
                            raise RuntimeError(f"{name}: {parsed['error']}")
                        return parsed
                return result.structuredContent

            names = {tool.name for tool in (await session.list_tools()).tools}
            required = {
                "draw_safe_orthogonal_connector", "audit_scientific_layout",
                "export_scientific_figure",
            }
            if missing := sorted(required - names):
                raise RuntimeError(f"Missing safety tools: {missing}")

            await call("create_document", {"template": ""})
            await call("set_page_size", {"width": 7.0, "height": 3.0})
            shapes = [
                {
                    "id": "frame", "type": "rounded_rectangle",
                    "x1": 0.15, "y1": 0.18, "x2": 6.85, "y2": 2.82,
                    "semantic_role": "container",
                },
                {
                    "id": "source", "type": "rounded_rectangle",
                    "x1": 0.45, "y1": 1.30, "x2": 1.65, "y2": 1.78,
                    "text": "Source", "semantic_role": "backbone",
                },
                {
                    "id": "target", "type": "rounded_rectangle",
                    "x1": 1.55, "y1": 1.30, "x2": 2.75, "y2": 1.78,
                    "text": "Target", "semantic_role": "exit",
                },
                {
                    "id": "obstacle", "type": "rounded_rectangle",
                    "x1": 3.55, "y1": 1.12, "x2": 4.45, "y2": 1.96,
                    "text": "Do not cross\nthis module", "semantic_role": "highlight",
                },
                {
                    "id": "finish", "type": "rounded_rectangle",
                    "x1": 5.45, "y1": 1.30, "x2": 6.55, "y2": 1.78,
                    "text": "Finish", "semantic_role": "accept",
                },
                {
                    "id": "note", "type": "text_box",
                    "x1": 1.0, "y1": 0.42, "x2": 6.0, "y2": 0.75,
                    "text": "Automatic target spacing + obstacle-aware routing + pre-export audit",
                    "font_size": "8.5 pt", "italic": True,
                },
            ]
            drawn = await call("batch_draw_shapes", {"shapes": json.dumps(shapes)})
            refs = drawn["ref_map"]
            connected = await call("batch_connect_shapes", {
                "connections": json.dumps([{
                    "from": "source", "to": "target", "semantic_role": "data_flow",
                    "route_style": "straight", "connector_appearance": "straight",
                }]),
                "ref_map": json.dumps(refs),
                "enforce_clearance": True,
                "min_clearance": 0.16,
            })
            safe = await call("draw_safe_orthogonal_connector", {
                "from_shape_id": refs["target"], "to_shape_id": refs["finish"],
                "obstacle_ids": [refs["obstacle"]], "preferred_axis": "horizontal",
                "clearance": 0.12,
                "role": "decision_flow",
            })
            audit = await call("audit_scientific_layout", {
                "min_control_gap": 0.14, "connector_clearance": 0.03,
                "min_connector_length": 0.12,
                "corner_exclusion": 0.10,
            })
            if audit["status"] != "pass":
                raise RuntimeError(json.dumps(audit, ensure_ascii=False, indent=2))

            vsdx = OUT / "visio_mcp_layout_safety_verified.vsdx"
            svg = OUT / "visio_mcp_layout_safety_verified.svg"
            png = OUT / "visio_mcp_layout_safety_verified.png"
            await call("save_document_as", {"file_path": str(vsdx)})
            exported = await call("export_scientific_figure", {
                "output_paths": json.dumps([str(svg), str(png)]), "strict": True,
                "min_control_gap": 0.14, "connector_clearance": 0.03,
                "min_connector_length": 0.12,
                "corner_exclusion": 0.10,
            })
            if not exported["exported"]:
                raise RuntimeError(json.dumps(exported, ensure_ascii=False, indent=2))
            print(json.dumps({
                "tool_count": len(names),
                "auto_adjustment": connected[0].get("layout_adjustment"),
                "safe_route": safe["route_points"],
                "audit": audit,
                "outputs": [str(vsdx), str(svg), str(png)],
            }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
