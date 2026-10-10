"""Root entry point — delegates to src/converter.py. Run with: python main.py"""

import sys
from src.converter import *


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_interactive_flow(auto_mode="--auto" in sys.argv)
    else:
        force_legacy = "--legacy-gui" in sys.argv
        launch_gui(auto_mode_init="--auto" in sys.argv, force_legacy=force_legacy)
