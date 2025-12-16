"""Completers for CLI prompt input."""

from langrepl.cli.completers.reference import ReferenceCompleter
from langrepl.cli.completers.router import CompleterRouter
from langrepl.cli.completers.slash import SlashCommandCompleter

__all__ = ["CompleterRouter", "ReferenceCompleter", "SlashCommandCompleter"]
