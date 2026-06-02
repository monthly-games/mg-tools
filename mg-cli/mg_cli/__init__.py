"""Importable package shim for the mg-cli source directory."""

from pathlib import Path

__version__ = "0.1.0"
__author__ = "Monthly Games"

_SOURCE_ROOT = Path(__file__).resolve().parent.parent
__path__.append(str(_SOURCE_ROOT))
