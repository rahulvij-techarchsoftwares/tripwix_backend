"""
MCP server implementation that is compatible with Python 3.8+.
This module contains the core infrastructure for the Model Context Protocol server.
"""

import asyncio
import inspect
import json
import logging
import sys
import traceback
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, TypeVar, get_type_hints

from .version import __version__

# Set up logging
logger = logging.getLogger("kolo.mcp")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Define protocol constants
PROTOCOL_VERSION = "2024-11-05"

# Type definitions
T = TypeVar("T")
ToolFunc = Callable[..., Any]


@dataclass
class Tool:
    """Representation of a tool in the MCP protocol."""

    name: str
    func: ToolFunc
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPServerInfo:
    """Server information for MCP protocol."""

    name: str
    version: str = ""

    def __post_init__(self):
        if not self.version:
            self.version = __version__


@dataclass
class MCPCapabilities:
    """Capabilities supported by the MCP server."""

    experimental: Dict[str, Any] = field(default_factory=dict)
    prompts: Dict[str, bool] = field(default_factory=lambda: {"listChanged": False})
    resources: Dict[str, bool] = field(
        default_factory=lambda: {"subscribe": False, "listChanged": False}
    )
    tools: Dict[str, bool] = field(default_factory=lambda: {"listChanged": False})
    roots: Dict[str, bool] = field(default_factory=lambda: {"listChanged": False})
    sampling: Dict[str, Any] = field(default_factory=dict)


class MCPServer:
    """A minimal implementation of the Model Context Protocol server compatible with Python 3.8+."""

    def __init__(self, name: str):
        self.server_info = MCPServerInfo(name=name)
        self.capabilities = MCPCapabilities()
        self.tools: Dict[str, Tool] = {}
        logger.info(f"Initialized MCP server with name: {name}")

    def tool(self) -> Callable[[ToolFunc], ToolFunc]:
        """Decorator to register a function as an MCP tool."""

        def decorator(func: ToolFunc) -> ToolFunc:
            tool_name = func.__name__
            type_hints = get_type_hints(func)
            description = func.__doc__ or ""

            # Extract parameter information
            sig = inspect.signature(func)
            properties = {}
            required = []

            for name, param in sig.parameters.items():
                if name == "self" or name == "cls":
                    continue

                param_type = type_hints.get(name, Any)
                prop: Dict[str, Any] = {}

                # Handle basic type annotations
                if param_type is inspect.Parameter.empty:
                    prop["type"] = "string"  # Default to string
                elif isinstance(param_type, type):
                    if issubclass(param_type, str):
                        prop["type"] = "string"
                    elif issubclass(param_type, int):
                        prop["type"] = "integer"
                    elif issubclass(param_type, float):
                        prop["type"] = "number"
                    elif issubclass(param_type, bool):
                        prop["type"] = "boolean"
                elif (
                    isinstance(param_type, List)
                    or getattr(param_type, "__origin__", None) is list
                ):
                    prop["type"] = "array"
                    # Create a separate dictionary for the items schema
                    # This fixes the type error where a Dict was being assigned to a str
                    item_type_dict = {"type": "string"}
                    prop["items"] = item_type_dict
                else:
                    # For complex types, we'll just use "object"
                    prop["type"] = "object"

                # Check if parameter has default (is optional)
                if param.default is inspect.Parameter.empty:
                    required.append(name)
                else:
                    # Add default value if available
                    if param.default is not None:
                        # Ensure default values have proper types in schema
                        if isinstance(param.default, bool):
                            # Make sure boolean defaults are properly typed
                            prop["default"] = param.default
                            # Force type to boolean for boolean defaults
                            prop["type"] = "boolean"
                        else:
                            prop["default"] = param.default

                properties[name] = prop

            # Create JSON schema for the tool
            input_schema = {
                "type": "object",
                "title": f"{tool_name}Arguments",
                "properties": properties,
            }

            if required:
                input_schema["required"] = required

            # Register the tool
            self.tools[tool_name] = Tool(
                name=tool_name,
                func=func,
                description=description,
                input_schema=input_schema,
            )

            logger.info(f"Registered tool: {tool_name}")
            return func

        return decorator

    async def handle_request(self, request_data: str) -> str:
        """Handle an incoming JSON-RPC request."""
        try:
            logger.debug(f"Handling request: {request_data.strip()}")

            # Parse the request data
            try:
                request = json.loads(request_data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                return self._error_response(None, -32700, f"Parse error: {str(e)}")

            # Extract JSON-RPC fields
            jsonrpc = request.get("jsonrpc")
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")

            logger.info(f"Processing method: {method} with id: {request_id}")

            if jsonrpc != "2.0":
                logger.warning(f"Invalid JSON-RPC version: {jsonrpc}")
                return self._error_response(
                    request_id, -32600, "Invalid Request: expected jsonrpc 2.0"
                )

            if method == "initialize":
                response = self._initialize_response(request_id)
                logger.debug(f"Initialize response JSON: {response}")
                return response
            elif method == "tools/list":
                response = self._tools_list_response(request_id)
                logger.debug(f"Tools list response JSON: {response}")
                return response
            elif method == "roots/list":
                # Handle roots/list request
                response = self._roots_list_response(request_id)
                logger.debug(f"Roots list response JSON: {response}")
                return response
            elif method == "tools/call":
                # Handle tools/call method (used by Anthropics MCP tool inspector)
                logger.info("Processing tools/call method")
                tool_name = params.get("name")
                tool_params = params.get(
                    "arguments", {}
                )  # Changed from parameters to arguments

                if not tool_name:
                    logger.warning("Tool name not provided in tools/call")
                    return self._error_response(
                        request_id, -32602, "Invalid params: tool name not provided"
                    )

                if tool_name not in self.tools:
                    logger.warning(f"Tool not found: {tool_name}")
                    return self._error_response(
                        request_id, -32601, f"Tool '{tool_name}' not found"
                    )

                logger.info(f"Executing tool via tools/call: {tool_name}")
                response = await self._execute_tool(request_id, tool_name, tool_params)
                logger.debug(f"Tool execution response JSON: {response}")
                return response
            elif method.startswith("notifications/"):
                # Handle notifications (like cancelled requests)
                notification_type = method.split("/")[1]
                logger.info(f"Received notification: {notification_type}")

                # No response needed for notifications as per JSON-RPC spec
                # Just acknowledge with an empty success response
                return json.dumps({"jsonrpc": "2.0", "id": request_id, "result": {}})
            elif method.startswith("tools/execute/"):
                tool_name = method.split("/")[-1]
                if tool_name not in self.tools:
                    logger.warning(f"Tool not found: {tool_name}")
                    return self._error_response(
                        request_id, -32601, f"Tool '{tool_name}' not found"
                    )

                logger.info(f"Executing tool: {tool_name}")
                response = await self._execute_tool(request_id, tool_name, params)
                logger.debug(f"Tool execution response JSON: {response}")
                return response
            else:
                logger.warning(f"Method not found: {method}")
                return self._error_response(
                    request_id, -32601, f"Method '{method}' not found"
                )

        except json.JSONDecodeError:
            logger.error("JSON parse error")
            return self._error_response(None, -32700, "Parse error")
        except Exception as e:
            logger.error(f"Internal error: {str(e)}")
            logger.error(traceback.format_exc())
            return self._error_response(None, -32603, f"Internal error: {str(e)}")

    def _initialize_response(self, request_id: Any) -> str:
        """Generate the initialize response with server info and capabilities."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": asdict(self.capabilities),
                "serverInfo": asdict(self.server_info),
            },
        }
        logger.debug(f"Initialize response: {response}")
        logger.debug(f"Server info: {asdict(self.server_info)}")
        logger.debug(f"Capabilities: {asdict(self.capabilities)}")
        return json.dumps(response)

    def _tools_list_response(self, request_id: Any) -> str:
        """Generate the tools/list response."""
        tools_list = []

        for name, tool in self.tools.items():
            tools_list.append(
                {
                    "name": name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
            )

        response = {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools_list}}
        logger.debug(f"Tools list response contains {len(tools_list)} tools")
        return json.dumps(response)

    def _roots_list_response(self, request_id: Any) -> str:
        """Generate the roots/list response."""
        roots_list = [
            {
                "id": "kolo",
                "name": "Kolo MCP Tools",
                "description": "Tools for deep Python tracing and debugging",
            }
        ]

        response = {"jsonrpc": "2.0", "id": request_id, "result": {"roots": roots_list}}
        logger.debug(f"Roots list response contains {len(roots_list)} roots")
        return json.dumps(response)

    async def _execute_tool(
        self, request_id: Any, tool_name: str, params: Dict[str, Any]
    ) -> str:
        """Execute a tool and return the response."""
        tool = self.tools.get(tool_name)
        if not tool:
            logger.warning(f"Tool not found for execution: {tool_name}")
            return self._error_response(
                request_id, -32601, f"Tool '{tool_name}' not found"
            )

        try:
            # Call the tool function with the provided parameters
            logger.info(f"Calling tool function: {tool_name}")
            logger.debug(f"Tool params: {params}")
            result = tool.func(**params)

            # Handle async functions
            if inspect.iscoroutine(result):
                logger.debug(f"Awaiting coroutine result for tool: {tool_name}")
                result = await result

            logger.info(f"Tool {tool_name} result: {result}")

            # Format the response according to MCP protocol
            if isinstance(result, List):
                # For lists, we need to format each item as a separate line item
                content_items = []
                for item in result:
                    content_items.append({"type": "text", "text": str(item)})

                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": content_items},
                }
            else:
                # For non-list results, use the standard format
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                                if isinstance(result, (str, int, float, bool))
                                else json.dumps(result),
                            }
                        ]
                    },
                }

            logger.info(f"Tool {tool_name} executed successfully")
            return json.dumps(response)

        except Exception as e:
            error_msg = f"Error executing tool {tool_name}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return self._error_response(request_id, -32603, error_msg)

    def _error_response(self, request_id: Any, code: int, message: str) -> str:
        """Generate an error response."""
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
        logger.debug(f"Error response: {response}")
        return json.dumps(response)

    async def read_stdin_line(self) -> str:
        """Read a line from stdin in an asynchronous way."""
        line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        logger.debug(f"Read line from stdin: {line.strip()}")
        return line

    async def run_stdio(self):
        """Run the server reading from stdin and writing to stdout."""
        logger.info("Starting MCP server on stdio transport")
        try:
            # Simpler approach based on the FastMCP implementation pattern
            while True:
                line = await self.read_stdin_line()
                if not line:
                    logger.info("Received empty line, exiting")
                    break

                if line.strip():
                    try:
                        if line.startswith("{"):
                            # Direct JSON-RPC request
                            request_data = line
                        else:
                            # Header-based request
                            if line.startswith("Content-Length:"):
                                content_length = int(line.strip().split(": ")[1])
                                # Skip empty line
                                await self.read_stdin_line()
                                # Read the content
                                request_data = (
                                    await asyncio.get_event_loop().run_in_executor(
                                        None,
                                        lambda: sys.stdin.buffer.read(
                                            content_length
                                        ).decode("utf-8"),
                                    )
                                )
                            else:
                                logger.warning(f"Invalid header: {line.strip()}")
                                continue

                        # Handle the request
                        response = await self.handle_request(request_data)

                        # Log the response for debugging
                        logger.debug(f"Response: {response}")

                        # Write response - always with newline for MCP tool inspector
                        sys.stdout.write(response)
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    except Exception as e:
                        logger.error(f"Error handling request: {e}")
                        logger.error(traceback.format_exc())

                        # Send error response
                        error_response = json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "error": {
                                    "code": -32603,
                                    "message": f"Internal error: {str(e)}",
                                },
                                "id": None,
                            }
                        )
                        sys.stdout.write(error_response)
                        sys.stdout.write("\n")
                        sys.stdout.flush()
        except Exception as e:
            logger.error(f"Fatal error in MCP server loop: {e}")
            logger.error(traceback.format_exc())
