"""Root entry point — delegates to src/converter.py. Run with: python main.py"""

from src.converter import *
import sys


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_interactive_flow(auto_mode="--auto" in sys.argv)
    else:
        launch_gui(auto_mode_init="--auto" in sys.argv)
