#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cell Tracking Analysis Pipeline - Main Entry Point

Usage:
    python main.py run <input_path> [options]
    python main.py --help
"""

from cell_tracker.cli import cli

if __name__ == '__main__':
    cli()
