from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

import httpx

from .db import (
    get_pinned_traces,
    list_traces_with_data_from_db,
    load_trace_with_size_from_db,
)
from .local_node_bridge import (
    process_node_data_with_local_node,
    process_trace_with_local_node,
    process_tree_with_local_node,
)
from .serialize import load_msgpack
from .utils import pretty_byte_size


def relative_time(timestamp: datetime) -> str:
    now = datetime.now(timezone.utc)

    delta = now - timestamp
    if delta.days > 7:
        relative_time = timestamp.strftime("%Y-%m-%d")
    elif delta.days > 0:
        relative_time = f"{delta.days}d ago"
    elif delta.seconds > 3600:
        relative_time = f"{delta.seconds // 3600}h ago"
    elif delta.seconds > 60:
        relative_time = f"{delta.seconds // 60}m ago"
    else:
        relative_time = f"{delta.seconds}s ago"

    return relative_time


def format_trace_for_display(
    trace_id: str,
    timestamp: datetime,
    size: int,
    trace_name: Optional[str],
    now: Optional[datetime] = None,
) -> str:
    """Format a trace for display in CLI or MCP."""
    if now is None:
        now = datetime.now(timezone.utc)

    rel_time = relative_time(timestamp)

    size_str = pretty_byte_size(size)

    # Format output with trace_id at the end if we have a name
    if trace_name:
        return f"{trace_name} ({rel_time}, {size_str}, {trace_id})"
    return f"{trace_id} ({rel_time}, {size_str})"


def get_formatted_traces(
    db_path, count: int = 500, reverse: bool = False
) -> Iterator[str]:
    """Get formatted traces from the database, yielding one at a time."""
    now = datetime.now(timezone.utc)
    traces = list_traces_with_data_from_db(db_path, count=count, reverse=reverse)

    for trace_id, timestamp_str, size, msgpack_data in traces:
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f").replace(
            tzinfo=timezone.utc
        )

        # Extract trace name if available
        trace_name = None
        if msgpack_data:
            data = load_msgpack(msgpack_data)
            if isinstance(data, dict) and "trace_name" in data and data["trace_name"]:
                trace_name = data["trace_name"]

        yield format_trace_for_display(trace_id, timestamp, size, trace_name, now)


local_cf_worker_endpoint = "http://localhost:8787"
prod_cf_worker_endpoint = "https://worker.kolo.app"
worker_endpoint = prod_cf_worker_endpoint


async def get_compact_trace(
    trace_id: str,
    trace_data: bytes,
    timestamp_str: str,
    size: int,
    include_returns: bool = False,
) -> str:
    """Get compact representation of a trace.

    First tries to use local Node.js if available, then falls back to remote worker.
    """
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f").replace(
        tzinfo=timezone.utc
    )

    prefix = f"{relative_time(timestamp)}, {pretty_byte_size(size)}"

    # Try local Node.js processing first
    compact_trace_text = process_trace_with_local_node(trace_data, include_returns)

    # Fall back to remote worker if local processing failed
    if compact_trace_text is None:
        compact_trace_text = await fetch_compact_trace(
            trace_id, trace_data, include_returns
        )

    return prefix + "\n\n" + compact_trace_text


async def fetch_compact_trace(
    trace_id: str, trace_data: bytes, include_returns: bool = False
) -> str:
    """Get compact representation of a trace from the worker."""

    async with httpx.AsyncClient() as client:
        url = f"{worker_endpoint}/traces/{trace_id}/compact"
        if include_returns:
            url += "?returns=1"

        response = await client.post(
            url, headers={"Content-Type": "application/msgpack"}, content=trace_data
        )
        response.raise_for_status()
        return response.text


async def get_node_data(trace_id: str, node_index: int, trace_data: bytes) -> dict:
    """Get node data from the worker for a specific node index.

    First tries to use local Node.js if available, then falls back to remote worker.
    """
    # Try local Node.js processing first
    node_data = process_node_data_with_local_node(trace_data, node_index)

    # Fall back to remote worker if local processing failed
    if node_data is None:
        node_data = await fetch_node_data(trace_id, node_index, trace_data)

    return node_data


async def fetch_node_data(trace_id: str, node_index: int, trace_data: bytes) -> dict:
    """Get node data from the remote worker for a specific node index."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker_endpoint}/traces/{trace_id}/tree/{node_index}",
            headers={"Content-Type": "application/msgpack"},
            content=trace_data,
        )
        response.raise_for_status()
        return response.json()


# Note: We're not yet using these to get the full tree.
# But let's add it.
async def get_execution_tree(trace_id: str, trace_data: bytes) -> dict:
    """Get execution tree for a trace.

    First tries to use local Node.js if available, then falls back to remote worker.
    """
    # Try local Node.js processing first
    tree_data = process_tree_with_local_node(trace_data)

    # Fall back to remote worker if local processing failed
    if tree_data is None:
        tree_data = await fetch_execution_tree(trace_id, trace_data)

    return tree_data


async def fetch_execution_tree(trace_id: str, trace_data: bytes) -> dict:
    """Get execution tree from the remote worker."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker_endpoint}/traces/{trace_id}/tree",
            headers={"Content-Type": "application/msgpack"},
            content=trace_data,
        )
        response.raise_for_status()
        return response.json()


async def get_compact_traces(
    db_path: Path,
    trace_id: Union[str, None] = None,
    *,
    pinned: bool = False,
    returns: bool = False,
    recent: int = 0,
) -> List[Tuple[str, str]]:
    """Get compact representation of traces.

    Args:
        db_path: Path to the database
        trace_id: Specific trace ID to get, ignored if pinned=True or recent>0
        pinned: If True, get all pinned traces
        returns: Include return values in compact representation
        recent: If > 0, get the N most recent traces

    Returns:
        List of tuples (trace_id, compact_representation)

    Raises:
        TraceNotFoundError: If trace_id is not found in the database
        ValueError: If no valid selection criteria provided
    """
    if not any([pinned, trace_id, recent > 0]):
        raise ValueError("Either trace_id, --pinned, or --recent must be provided")
    results = []

    if pinned:
        for trace_id, timestamp_str, size, trace_data in get_pinned_traces(db_path):
            try:
                compact_repr = await get_compact_trace(
                    trace_id, trace_data, timestamp_str, size, returns
                )
                results.append((trace_id, compact_repr))
            except Exception as e:
                # For pinned traces, we want to continue even if one fails
                results.append((trace_id, f"Error: {e}"))
    elif recent > 0:
        for trace_id, timestamp_str, size, trace_data in list_traces_with_data_from_db(
            db_path, count=recent
        ):
            assert trace_id is not None
            try:
                compact_repr = await get_compact_trace(
                    trace_id, trace_data, timestamp_str, size, returns
                )
                results.append((trace_id, compact_repr))
            except Exception as e:
                # For multiple traces, we want to continue even if one fails
                results.append((trace_id, f"Error: {e}"))
    else:
        # Single trace - let errors propagate naturally
        assert trace_id is not None
        _, timestamp_str, size, trace_data = load_trace_with_size_from_db(
            db_path, trace_id
        )
        compact_repr = await get_compact_trace(
            trace_id, trace_data, timestamp_str, size, returns
        )
        results.append((trace_id, compact_repr))

    return results
