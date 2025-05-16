from typing import Dict, List

from .cli_mcp_shared import get_compact_trace as aget_compact_trace
from .cli_mcp_shared import get_compact_traces, get_formatted_traces, get_node_data
from .db import get_db_path, load_trace_from_db, load_trace_with_size_from_db, setup_db
from .mcp_plumbing import MCPServer

# Create a global MCP server instance
mcp = MCPServer("kolo")


@mcp.tool()
async def get_compact_trace(trace_id: str, include_returns: bool = False) -> str:
    """Get a compact representation of a specific trace.

    This is useful when you need to understand what happened in a specific trace,
    identified by its trace_id. The compact representation shows the sequence of
    function calls and their outcomes.

    Args:
        trace_id: ID of the trace to get
        include_returns: Whether to include return values (warning: can be verbose)

    Example:
        >>> get_compact_trace("trc_1234567890")
        "main() -> process_data() -> validate_input() -> ..."
    """
    db_path = get_db_path()
    _, timestamp_str, size, trace_data = load_trace_with_size_from_db(db_path, trace_id)
    return await aget_compact_trace(
        trace_id=trace_id,
        trace_data=trace_data,
        timestamp_str=timestamp_str,
        size=size,
        include_returns=include_returns,
    )


@mcp.tool()
async def get_trace_node(trace_id: str, node_index: int) -> Dict:
    """Get detailed information about a specific node in a trace.

    This is useful when you need to deeply understand what happened at a specific
    point in the execution, like examining function arguments, local variables,
    or the exact line of code being executed.

    Args:
        trace_id: ID of the trace containing the node
        node_index: Index of the node in the trace tree

    Example:
        >>> get_trace_node("trc_123", 5)
        {"type": "call", "function": "validate_input", "args": {"data": {...}}, ...}
    """
    db_path = get_db_path()
    trace_data, _ = load_trace_from_db(db_path, trace_id)
    return await get_node_data(trace_id, node_index, trace_data)


@mcp.tool()
async def get_pinned_traces(include_returns: bool = False) -> List[str]:
    """Get compact representations of all pinned traces.

    This is useful for understanding the key execution paths that have been marked
    as important. Pinned traces often represent core functionality or critical
    paths through the codebase.

    Args:
        include_returns: Whether to include return values (warning: can be verbose)

    Example:
        >>> get_pinned_traces()
        [
            "main() -> process_data() -> ...",
            "test() -> validate() -> ..."
        ]
    """
    db_path = get_db_path()
    traces = await get_compact_traces(db_path, pinned=True, returns=include_returns)
    return [compact for _, compact in traces]


@mcp.tool()
async def get_recent_compact_traces(
    count: int = 5, include_returns: bool = False
) -> List[str]:
    """
    Get the compact representation of the most recent traces.

    The traces are detailed call graphs of program execution. It's as if a debugger was active
    for the last 5 requests/program executions and every function call and return was logged.
    It includes extremely useful data about program execution flow, function arguments, return
    values, sql queries, and more.

    Use this tool to get unstuck and to understand how the just executed code actually behaved
    in practice. Use it to check assumptions or to answer the question "why" something didn't work.

    This tool call is cheap and fast, when in doubt, make it to gather extra info.

    Examples:
    - A 500 error happened. The kolo trace includes the full stack trace revealing why the error happened
    - Everything seems fine, but the user is reporting unexpected behaviour. The kolo trace reveals a codepath you
    didn't expect and need to account for.
    - You're debugging a complex issue and need to understand the flow of the program. The kolo trace shows you

    Warning: Setting include_returns=True with a large count can return a lot of data.

    Args:
        count: Number of recent traces to get (default: 5)
        include_returns: Whether to include return values (warning: can be verbose)

    Example:
        >>> get_recent_compact_traces(2)
        [
            "main() -> process_data() -> ...",
            "test() -> validate() -> ..."
        ]
    """
    db_path = get_db_path()
    traces = await get_compact_traces(db_path, recent=count, returns=include_returns)
    return [compact for _, compact in traces]


@mcp.tool()
def list_traces(count: int = 30) -> List[str]:
    """Concisely list available traces, ordered by most recent first.

    This is useful for getting an overview of what traces are available and
    finding specific traces you might want to analyze further.
    It's also useful to see recent activity. Traces may be named.
    Call this tool *often* to orient yourself and see where useful context may lie.
    After using this tool, call get_compact_trace to get more details about a specific trace.

    Args:
        count: How many traces to list (default: 30)

    Example:
        >>> list_traces(5)
        [
            "200 POST /buttons/poll_action/ (20h ago,   1.3 MB, trc_01JPMVDD0TRMW30JDAWR8HR4ZR)",
            "200 POST /poll/command/poll/ (20h ago, 321.1 KB, trc_01JPMVDAE8TA7N06JHJ809K2PE)",
            "200 POST /buttons/poll_action/vote/ (21h ago, 384.9 KB, trc_01JPMPK97J568NH2JZP5J2P02F)",
            "trc_01JPMKX2BEYZT7VM8A3FWC6DVK (22h ago, 346.8 KB)",
            "trc_01JPMKTVE3X7WRRE06Y2BDWXZ5 (22h ago, 346.8 KB)"
        ]
    """
    db_path = setup_db()

    # get_formatted_traces returns an iterator, not an awaitable
    formatted_traces = get_formatted_traces(db_path, count=count)
    return list(formatted_traces)
