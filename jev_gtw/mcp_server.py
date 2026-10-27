"""Small stdio MCP adapter; no endpoint serving unreviewed files or resources."""
import json


def create_server(service):
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult, ImageContent, TextContent

    server = FastMCP("jev-gtw", log_level="WARNING",
                     instructions="Use source handles to request reviewed views. A withheld view stays local.")

    def pack(result):
        safe = {k: v for k, v in result.items() if k != "image_base64"}
        content = [TextContent(type="text", text=json.dumps(safe, ensure_ascii=True))]
        if result.get("image_base64"):
            content.append(ImageContent(type="image", data=result["image_base64"], mimeType="image/png"))
        return CallToolResult(content=content, isError=False)

    @server.tool(name="gateway_sources")
    def sources() -> dict:
        """List operator-provided source handles and coarse access policy."""
        return service.catalog()

    @server.tool(name="gateway_read")
    def read(source_id: str) -> CallToolResult:
        """Request a text/image view. Protected content is withheld before it reaches the agent."""
        return pack(service.read(source_id))

    @server.tool(name="gateway_compute")
    def compute(source_ids: list[str], code: str) -> CallToolResult:
        """Run Python in the configured sandbox. Inputs: /inputs/<id>; outputs: /outputs.

        Captured output is reviewed. Saved artifacts remain private. No configured
        sandbox means no execution. Never infer computation success from withholding.
        """
        return pack(service.compute(source_ids, code))

    return server

