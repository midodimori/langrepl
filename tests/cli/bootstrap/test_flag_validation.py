"""Tests for CLI flag validation."""

import argparse
from unittest.mock import MagicMock

import pytest

from langrepl.cli.bootstrap.app import _validate_server_args
from langrepl.configs import ApprovalMode


@pytest.fixture
def parser():
    return argparse.ArgumentParser()


class TestServerFlagValidation:
    """Tests for _validate_server_args."""

    def test_rejects_resume_in_server_mode(self, parser):
        args = MagicMock(
            resume=True,
            message=None,
            model=None,
            agent=None,
            approval_mode=ApprovalMode.SEMI_ACTIVE.value,
        )
        with pytest.raises(SystemExit):
            _validate_server_args(parser, args)

    def test_rejects_message_in_server_mode(self, parser):
        args = MagicMock(
            resume=False,
            message="hello",
            model=None,
            agent=None,
            approval_mode=ApprovalMode.SEMI_ACTIVE.value,
        )
        with pytest.raises(SystemExit):
            _validate_server_args(parser, args)

    def test_rejects_model_without_agent(self, parser):
        args = MagicMock(
            resume=False,
            message=None,
            model="gpt-4o",
            agent=None,
            approval_mode=ApprovalMode.SEMI_ACTIVE.value,
        )
        with pytest.raises(SystemExit):
            _validate_server_args(parser, args)

    def test_rejects_approval_mode_without_agent(self, parser):
        args = MagicMock(
            resume=False,
            message=None,
            model=None,
            agent=None,
            approval_mode=ApprovalMode.AGGRESSIVE.value,
        )
        with pytest.raises(SystemExit):
            _validate_server_args(parser, args)

    def test_accepts_valid_server_args(self, parser):
        args = MagicMock(
            resume=False,
            message=None,
            model=None,
            agent=None,
            approval_mode=ApprovalMode.SEMI_ACTIVE.value,
        )
        _validate_server_args(parser, args)  # should not raise

    def test_accepts_agent_with_model(self, parser):
        args = MagicMock(
            resume=False,
            message=None,
            model="gpt-4o",
            agent="general",
            approval_mode=ApprovalMode.SEMI_ACTIVE.value,
        )
        _validate_server_args(parser, args)  # should not raise

    def test_accepts_agent_with_approval_mode(self, parser):
        args = MagicMock(
            resume=False,
            message=None,
            model=None,
            agent="general",
            approval_mode=ApprovalMode.AGGRESSIVE.value,
        )
        _validate_server_args(parser, args)  # should not raise
