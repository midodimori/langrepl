"""Dispatchers for routing user inputs."""

from langrepl.cli.dispatchers.commands import CommandDispatcher
from langrepl.cli.dispatchers.messages import MessageDispatcher

__all__ = ["CommandDispatcher", "MessageDispatcher"]
