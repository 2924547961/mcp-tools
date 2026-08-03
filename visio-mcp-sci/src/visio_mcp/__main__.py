"""Allow running visio_mcp as a module: python -m visio_mcp"""

from visio_mcp.visio_server import mcp

mcp.run(transport="stdio")
