#!/usr/bin/env python3
"""
Entry point for running Synapse as a module.

Usage:
    python -m synapse <command> [options]
"""

from .cli import main

if __name__ == "__main__":
    main()
