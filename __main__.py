"""
Entry point for `python .` from the project root (same as `python main.py`).
"""

import sys
from src.converter import cli_interactive_flow, launch_gui

if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_interactive_flow(auto_mode="--auto" in sys.argv)
    else:
        launch_gui(auto_mode_init="--auto" in sys.argv)
