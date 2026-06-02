"""
Entry point for mg_cli package.

Usage:
    python -m mg_cli [command] [options]

Or via installed command:
    mg-cli [command] [options]
"""

from .cli import main

if __name__ == "__main__":
    main()
