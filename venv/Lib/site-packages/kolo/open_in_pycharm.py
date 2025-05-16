import glob
import os
import subprocess
import sys

# We open VS Code source code through a URI scheme directly from the frontend.
# However, such a scheme doesn't seem to exist for PyCharm.
# This is the most reliable approach I managed to find for opening PyCharm files.


def get_pycharm_executable():
    """Get the PyCharm executable path based on the operating system."""
    if sys.platform.startswith("win"):
        # Windows: Check common installation directories
        common_paths = [
            r"C:\Program Files\JetBrains\PyCharm*\bin\pycharm64.exe",
            r"C:\Program Files (x86)\JetBrains\PyCharm*\bin\pycharm.exe",
        ]
        for path in common_paths:
            matches = sorted(glob.glob(path), reverse=True)
            if matches:
                return matches[0]
    elif sys.platform.startswith("darwin"):
        # macOS
        return "/Applications/PyCharm.app/Contents/MacOS/pycharm"
    else:
        # Linux
        return "pycharm"  # Assumes PyCharm is in PATH


def get_project_path(file_path):
    """
    Attempt to find the PyCharm project path by looking for .idea directory
    or a pyproject.toml file in parent directories.
    """
    current_dir = os.path.dirname(os.path.abspath(file_path))
    while current_dir != os.path.dirname(current_dir):  # Stop at root directory
        if os.path.exists(os.path.join(current_dir, ".idea")):
            return current_dir
        if os.path.exists(os.path.join(current_dir, "pyproject.toml")):
            return current_dir
        current_dir = os.path.dirname(current_dir)
    return None  # If no project directory found


class OpenInPyCharmError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def open_in_pycharm(file_path):
    pycharm_exe = get_pycharm_executable()
    if not pycharm_exe:
        raise OpenInPyCharmError("PyCharm executable not found.")

    project_path = get_project_path(file_path)
    if not project_path:
        # Unable to determine project path. Opening file directly.
        project_path = os.path.dirname(file_path)

    cmd = [pycharm_exe, project_path, file_path]

    try:
        subprocess.Popen(cmd)
    except Exception as e:
        OpenInPyCharmError(f"Error opening PyCharm: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python open_in_pycharm.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    open_in_pycharm(file_path)
