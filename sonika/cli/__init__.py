"""Sonika CLI — entry point for the `sonika` command."""

from sonika.cli.tui import SonikaApp


def main():
    SonikaApp().run(mouse=False)
