"""Sonika CLI — entry point for the `sonika` command."""

import asyncio


def main():
    from sonika.cli.app import SonikaCLI
    try:
        asyncio.run(SonikaCLI().run())
    except (KeyboardInterrupt, EOFError):
        pass
