"""Entry point for running the package as a module or standalone executable.

This module uses absolute imports to work correctly when:
1. Run as `python -m onepace_assistant`
2. Built as a standalone executable with Nuitka
"""

from onepace_assistant.cli import main

if __name__ == "__main__":
    main()
