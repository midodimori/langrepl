"""Tests for performance timer module."""

from unittest.mock import patch

import pytest

from src.cli.bootstrap.timer import _Timer, enable_timer, timer


@pytest.fixture
def mock_console():
    """Mock console for timer tests."""
    with patch("src.cli.bootstrap.timer.console.console") as mock_console:
        yield mock_console


@pytest.fixture
def mock_perf_counter():
    """Mock perf_counter that returns 0.0, then 1.5 seconds."""
    with patch(
        "src.cli.bootstrap.timer.time.perf_counter", side_effect=[0.0, 1.5]
    ) as mock:
        yield mock


@pytest.fixture
def timer_module_state():
    """Save and restore timer module's _enabled state."""
    import src.cli.bootstrap.timer as timer_module

    initial_state = timer_module._enabled
    yield timer_module
    timer_module._enabled = initial_state


class TestTimer:
    """Tests for _Timer class."""

    def test_timer_measures_elapsed_time(self, mock_console, mock_perf_counter):
        """Test that _Timer measures elapsed time."""
        timer_instance = _Timer("Test phase", enabled=True)

        with timer_instance:
            pass

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Test phase" in call_args
        assert "1.500s" in call_args

    def test_timer_does_nothing_when_disabled(self, mock_console):
        """Test that _Timer does nothing when disabled."""
        timer_instance = _Timer("Test phase", enabled=False)

        with timer_instance:
            pass

        mock_console.print.assert_not_called()

    def test_timer_enter_returns_self(self):
        """Test that __enter__ returns self."""
        timer_instance = _Timer("Test phase", enabled=False)

        result = timer_instance.__enter__()

        assert result is timer_instance

    @patch("src.cli.bootstrap.timer.time.perf_counter", side_effect=[0.0, 1.0])
    def test_timer_handles_exception_in_context(
        self,
        _mock_perf_counter,
        mock_console,
    ):
        """Test that _Timer handles exceptions in context."""
        timer_instance = _Timer("Test phase", enabled=True)

        try:
            with timer_instance:
                raise ValueError("Test error")
        except ValueError:
            pass

        mock_console.print.assert_called_once()

    @patch(
        "src.cli.bootstrap.timer.time.perf_counter",
        side_effect=[0.0, 0.123456],
    )
    def test_timer_formats_time_with_three_decimals(
        self,
        _mock_perf_counter,
        mock_console,
    ):
        """Test that _Timer formats time with three decimal places."""
        timer_instance = _Timer("Test phase", enabled=True)

        with timer_instance:
            pass

        call_args = mock_console.print.call_args[0][0]
        assert "0.123s" in call_args

    def test_timer_stores_phase_name(self):
        """Test that _Timer stores phase name."""
        timer_instance = _Timer("My Phase", enabled=True)

        assert timer_instance.phase_name == "My Phase"

    def test_timer_stores_enabled_flag(self):
        """Test that _Timer stores enabled flag."""
        timer_enabled = _Timer("Phase", enabled=True)
        timer_disabled = _Timer("Phase", enabled=False)

        assert timer_enabled.enabled is True
        assert timer_disabled.enabled is False


class TestEnableTimer:
    """Tests for enable_timer function."""

    def test_enable_timer_sets_global_flag(self, timer_module_state):
        """Test that enable_timer sets global _enabled flag."""
        enable_timer()

        assert timer_module_state._enabled is True

    def test_enable_timer_affects_timer_function(self, timer_module_state):
        """Test that enable_timer affects timer() function behavior."""
        timer_module_state._enabled = False
        timer_disabled = timer("Test")
        assert timer_disabled.enabled is False

        enable_timer()
        timer_enabled = timer("Test")
        assert timer_enabled.enabled is True


class TestTimerFunction:
    """Tests for timer function."""

    def test_timer_function_returns_timer_instance(self):
        """Test that timer() returns _Timer instance."""
        result = timer("Test phase")

        assert isinstance(result, _Timer)

    def test_timer_function_passes_phase_name(self):
        """Test that timer() passes phase name to _Timer."""
        result = timer("My Phase Name")

        assert result.phase_name == "My Phase Name"

    def test_timer_function_respects_global_enabled_flag(self, timer_module_state):
        """Test that timer() respects global _enabled flag."""
        timer_module_state._enabled = False
        result_disabled = timer("Test")
        assert result_disabled.enabled is False

        timer_module_state._enabled = True
        result_enabled = timer("Test")
        assert result_enabled.enabled is True

    def test_timer_function_can_be_used_as_context_manager(self, timer_module_state):
        """Test that timer() can be used as context manager."""
        timer_module_state._enabled = False

        with timer("Test phase"):
            pass

    @patch(
        "src.cli.bootstrap.timer.time.perf_counter",
        side_effect=[0.0, 2.5],
    )
    def test_timer_function_prints_when_enabled(
        self,
        _mock_perf_counter,
        timer_module_state,
        mock_console,
    ):
        """Test that timer() prints timing info when enabled."""
        timer_module_state._enabled = True

        with timer("Load config"):
            pass

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Load config" in call_args
        assert "2.500s" in call_args

    def test_timer_function_does_not_print_when_disabled(
        self, timer_module_state, mock_console
    ):
        """Test that timer() does not print when disabled."""
        timer_module_state._enabled = False

        with timer("Load config"):
            pass

        mock_console.print.assert_not_called()

    @patch(
        "src.cli.bootstrap.timer.time.perf_counter",
        side_effect=[0.0, 1.0, 2.0, 3.5],
    )
    def test_timer_function_multiple_timers_independent(
        self,
        _mock_perf_counter,
        timer_module_state,
        mock_console,
    ):
        """Test that multiple timers are independent."""
        timer_module_state._enabled = True

        with timer("Phase 1"):
            pass

        with timer("Phase 2"):
            pass

        assert mock_console.print.call_count == 2

        first_call = mock_console.print.call_args_list[0][0][0]
        second_call = mock_console.print.call_args_list[1][0][0]

        assert "Phase 1" in first_call
        assert "1.000s" in first_call
        assert "Phase 2" in second_call
        assert "1.500s" in second_call
