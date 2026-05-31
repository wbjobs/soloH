#!/usr/bin/env python
"""
Eddy Current Testing Signal Analysis Tool - Main Entry Point.

This tool provides a comprehensive suite for eddy current testing signal
processing, including data loading, preprocessing, feature extraction,
crack detection, and report generation.

Usage:
    python main.py [command] [options]

For help:
    python main.py --help
    python main.py [command] --help
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from eddytester.cli import cli

if __name__ == "__main__":
    cli()
