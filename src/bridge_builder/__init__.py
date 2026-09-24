"""Workshop Bridge Builder: pygame window + MCP HTTP server."""

from bridge_builder.client import MCP_URL, call_tool, list_tools, register_claude

__version__ = "0.1.0"

__all__ = ["MCP_URL", "__version__", "call_tool", "list_tools", "register_claude"]
