"""
Entry point for mg_cli package.

Usage:
    python -m mg-cli [command] [options]

Or via installed command:
    mg-cli [command] [options]
"""

from .cli import cli

if __name__ == "__main__":
    cli()
