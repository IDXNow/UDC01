#!/usr/bin/env python3
"""
Universal Data Converter (UDC01) - CLI Entry Point
---------------------------------------------------
Command-line interface for the UDC01 data transformation framework.

Usage:
    python udc01.py --file <input_file> [options]
    python udc01.py --folder <folder> --pattern <pattern> [options]

For detailed usage information, run:
    python udc01.py --help
"""

from udc01.converter import main

if __name__ == "__main__":
    main()
