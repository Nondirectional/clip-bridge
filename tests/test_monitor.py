"""Tests for monitor module."""

import time
from unittest.mock import MagicMock, patch

import pytest

from clip_bridge import monitor as monitor_module

# Mock pyperclip at module level before Monitor class is used
mock_pyperclip = MagicMock()
monitor_module.pyperclip = mock_pyperclip

from clip_bridge.monitor import Monitor


class TestMonitorInit:
    """Tests for Monitor initialization."""

    def test_monitor_initializes_with_defaults(self):
        """Monitor initializes with default values."""
        monitor = Monitor()

        assert monitor._interval == 0.5
        assert monitor._on_change is None
        assert monitor._last_content == ""
        assert monitor._running is False
        assert monitor._thread is None

    def test_monitor_initializes_with_custom_interval(self):
        """Monitor initializes with custom interval."""
        monitor = Monitor(interval=1.0)

        assert monitor._interval == 1.0

    def test_monitor_initializes_with_callback(self):
        """Monitor initializes with callback."""
        callback = MagicMock()
        monitor = Monitor(on_change=callback)

        assert monitor._on_change is callback


class TestMonitorStart:
    """Tests for start method."""

    def test_start_creates_daemon_thread(self):
        """start() creates a daemon thread."""
        monitor = Monitor(interval=0.1)

        monitor.start()

        assert monitor._thread is not None
        assert monitor._thread.is_alive()
        assert monitor._thread.daemon
        assert monitor._running is True

        monitor.stop()

    def test_start_calls_callback_on_change(self):
        """Monitor calls callback when clipboard content changes."""
        callback = MagicMock()
        monitor = Monitor(interval=0.1, on_change=callback)

        # Initial clipboard state
        mock_pyperclip.paste.return_value = "initial"

        monitor.start()
        time.sleep(0.2)  # Wait for at least one poll

        # Callback should not be called yet (no change from initial state)
        callback.assert_not_called()

        # Change clipboard content
        mock_pyperclip.paste.return_value = "new content"
        time.sleep(0.2)  # Wait for detection

        callback.assert_called_once_with("new content")

        monitor.stop()

    def test_start_with_no_callback(self):
        """Monitor runs without crashing when no callback is set."""
        monitor = Monitor(interval=0.1)

        mock_pyperclip.paste.return_value = "test"
        monitor.start()
        time.sleep(0.2)

        # Should not crash, just run without callback
        assert monitor._running is True

        monitor.stop()


class TestMonitorStop:
    """Tests for stop method."""

    def test_stop_stops_monitor_thread(self):
        """stop() stops the monitor thread."""
        monitor = Monitor(interval=0.1)
        monitor.start()

        assert monitor._running is True
        assert monitor._thread is not None
        assert monitor._thread.is_alive()

        monitor.stop()
        time.sleep(0.1)  # Give thread time to stop

        assert monitor._running is False

    def test_stop_is_idempotent(self):
        """stop() can be called multiple times safely."""
        monitor = Monitor(interval=0.1)
        monitor.start()

        monitor.stop()
        monitor.stop()  # Should not raise

        assert monitor._running is False


class TestMonitorDetectsChanges:
    """Tests for change detection."""

    def test_monitor_detects_changes(self):
        """Monitor detects clipboard change and calls callback."""
        callback = MagicMock()
        monitor = Monitor(interval=0.1, on_change=callback)

        mock_pyperclip.paste.return_value = "content1"

        monitor.start()
        time.sleep(0.2)

        # Change content
        mock_pyperclip.paste.return_value = "content2"
        time.sleep(0.2)

        callback.assert_called_with("content2")

        monitor.stop()


class TestMonitorIgnoresDuplicates:
    """Tests for duplicate content handling."""

    def test_monitor_ignores_duplicates(self):
        """Monitor does not trigger callback for same content."""
        callback = MagicMock()
        monitor = Monitor(interval=0.1, on_change=callback)

        mock_pyperclip.paste.return_value = "same content"

        monitor.start()
        time.sleep(0.2)

        # Keep same content
        mock_pyperclip.paste.return_value = "same content"
        time.sleep(0.3)  # Multiple polls

        # Callback should only be called once (first detection)
        assert callback.call_count <= 1

        monitor.stop()


class TestMonitorUpdateLastContent:
    """Tests for update_last_content method."""

    def test_monitor_update_last_content(self):
        """update_last_content() updates the last tracked content."""
        callback = MagicMock()
        monitor = Monitor(interval=0.1, on_change=callback)

        mock_pyperclip.paste.return_value = "current"

        monitor.start()
        time.sleep(0.2)

        # Update last content externally
        monitor.update_last_content("updated")
        assert monitor._last_content == "updated"

        # Even though clipboard says "changed", it won't trigger
        # because last_content was updated to match
        mock_pyperclip.paste.return_value = "updated"
        time.sleep(0.2)

        # Should not trigger since we manually set last_content
        callback.assert_not_called()

        monitor.stop()


class TestMonitorThreadSafety:
    """Tests for thread safety."""

    def test_update_last_content_is_thread_safe(self):
        """update_last_content() works while monitor is running."""
        callback = MagicMock()
        monitor = Monitor(interval=0.05, on_change=callback)

        mock_pyperclip.paste.return_value = "test"
        monitor.start()

        # Update last_content multiple times while running
        for i in range(5):
            monitor.update_last_content(f"content_{i}")
            time.sleep(0.03)

        # Should not crash
        assert monitor._running is True

        monitor.stop()


class TestMonitorErrorHandling:
    """Tests for error handling."""

    def test_pyperclip_error_logged_does_not_crash(self):
        """pyperclip errors are logged but don't crash monitor."""
        monitor = Monitor(interval=0.1, on_change=MagicMock())

        mock_pyperclip.paste.side_effect = Exception("Clipboard error")
        monitor.start()
        time.sleep(0.3)

        # Monitor should still be running despite errors
        assert monitor._running is True

        monitor.stop()

    def test_callback_error_does_not_crash_monitor(self):
        """Errors in callback are logged but don't crash monitor."""
        failing_callback = MagicMock(side_effect=Exception("Callback error"))
        monitor = Monitor(interval=0.1, on_change=failing_callback)

        mock_pyperclip.paste.return_value = "initial"
        monitor.start()
        time.sleep(0.2)

        # Trigger callback (which will fail)
        mock_pyperclip.paste.return_value = "new content"
        time.sleep(0.2)

        # Monitor should still be running
        assert monitor._running is True

        monitor.stop()
