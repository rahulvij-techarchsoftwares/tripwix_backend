# Vibe coded file

import json
import os
import subprocess
import tempfile
from typing import Dict, Optional


def _get_node_js_path() -> Optional[str]:
    """Try to find the node.js executable on the system."""
    # Try 'node' command first
    result = subprocess.run(
        ["which", "node"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return result.stdout.strip()

    # Try 'nodejs' command on some Linux distributions
    result = subprocess.run(
        ["which", "nodejs"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return result.stdout.strip()

    # On Windows, we might need to look in common installation directories
    if os.name == "nt":
        potential_paths = [
            os.path.join(
                os.environ.get("ProgramFiles", "C:\\Program Files"),
                "nodejs",
                "node.exe",
            ),
            os.path.join(
                os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
                "nodejs",
                "node.exe",
            ),
            os.path.join(os.environ.get("APPDATA", ""), "npm", "node.exe"),
        ]
        for path in potential_paths:
            if os.path.isfile(path):
                return path

    return None


def _get_node_worker_path() -> str:
    """Get the path to the Node.js worker script bundled with kolo."""
    package_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(package_dir, "js", "kolo-js.js")


def process_trace_with_local_node(
    trace_data: bytes, include_returns: bool = False
) -> Optional[str]:
    """Process trace data using local Node.js installation."""
    node_path = _get_node_js_path()
    worker_script = _get_node_worker_path()

    if not node_path or not os.path.isfile(worker_script):
        return None

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(trace_data)
        temp_file_path = temp_file.name

    try:
        cmd = [node_path, worker_script, "compact", temp_file_path]
        if include_returns:
            cmd.append("--returns")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    finally:
        os.unlink(temp_file_path)


def process_node_data_with_local_node(
    trace_data: bytes, node_index: int
) -> Optional[dict]:
    """Process node data using local Node.js installation."""
    node_path = _get_node_js_path()
    worker_script = _get_node_worker_path()

    if not node_path or not os.path.isfile(worker_script):
        return None

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(trace_data)
        temp_file_path = temp_file.name

    try:
        cmd = [node_path, worker_script, "node", temp_file_path, str(node_index)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    finally:
        os.unlink(temp_file_path)


def process_tree_with_local_node(trace_data: bytes) -> Optional[Dict]:
    """Process execution tree using local Node.js installation."""
    node_path = _get_node_js_path()
    worker_script = _get_node_worker_path()

    if not node_path or not os.path.isfile(worker_script):
        return None

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(trace_data)
        temp_file_path = temp_file.name

    try:
        cmd = [node_path, worker_script, "tree", temp_file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    finally:
        os.unlink(temp_file_path)
