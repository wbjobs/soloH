#!/usr/bin/env python
"""
Emotional TTS - 情感语音合成命令行工具
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.inference.cli import main


if __name__ == "__main__":
    main()
