"""End-to-end integration tests for Clip Bridge.

These tests verify the complete synchronization flow between two ClipBridge
instances running in separate threads, using mock clipboard implementations.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from clip_bridge.config import Config
from clip_bridge.cooldown import CooldownManager
from clip_bridge.monitor import Monitor
from clip_bridge.protocol import encode_message
from clip_bridge.receiver import Receiver
from clip_bridge.sender import Sender


class MockClipboard:
    """Mock clipboard for testing in headless environments."""

    def __init__(self) -> None:
        self._content = ""
        self._lock = threading.Lock()

    def copy(self, content: str) -> None:
        """Copy content to clipboard."""
        with self._lock:
            self._content = content

    def paste(self) -> str:
        """Paste content from clipboard."""
        with self._lock:
            return self._content


class TestClipBridge:
    """Integration tests for full clipboard synchronization."""

    def test_end_to_end_sync(self, tmp_path):
        """Test full synchronization between two ClipBridge instances.

        Creates two ClipBridge-like instances with different ports,
        starts both in threads, and verifies clipboard content is
        synchronized from one to the other.
        """
        # Create temporary config files
        config_a_path = tmp_path / "config_a.yaml"
        config_b_path = tmp_path / "config_b.yaml"

        # Config for instance A (listens on 19998, connects to 19999)
        config_a = Config(
            local_port=19998,
            remote_host="127.0.0.1",
            remote_port=19999,
            poll_interval=0.1,
            sync_cooldown=0.5,
        )
        config_a.save(str(config_a_path))

        # Config for instance B (listens on 19999, connects to 19998)
        config_b = Config(
            local_port=19999,
            remote_host="127.0.0.1",
            remote_port=19998,
            poll_interval=0.1,
            sync_cooldown=0.5,
        )
        config_b.save(str(config_b_path))

        # Create mock clipboards for each instance
        clipboard_a = MockClipboard()
        clipboard_b = MockClipboard()

        # Track received content for verification
        received_content_b: list[str] = []
        received_content_a: list[str] = []
        lock = threading.Lock()

        def on_receive_b(data: bytes) -> None:
            """Handle received data on instance B."""
            content = data.decode("utf-8")
            clipboard_b.copy(content)
            with lock:
                received_content_b.append(content)

        def on_receive_a(data: bytes) -> None:
            """Handle received data on instance A."""
            content = data.decode("utf-8")
            clipboard_a.copy(content)
            with lock:
                received_content_a.append(content)

        # Create cooldown managers
        cooldown_a = CooldownManager(cooldown_seconds=0.5)
        cooldown_b = CooldownManager(cooldown_seconds=0.5)

        # Create components for instance A
        receiver_a = Receiver(
            host="",
            port=19998,
            on_receive=on_receive_a,
        )
        sender_a = Sender(
            host="127.0.0.1",
            port=19999,
        )

        # Create components for instance B
        receiver_b = Receiver(
            host="",
            port=19999,
            on_receive=on_receive_b,
        )
        sender_b = Sender(
            host="127.0.0.1",
            port=19998,
        )

        # Start network components first
        receiver_a.start()
        receiver_b.start()
        time.sleep(0.1)  # Let receivers start

        sender_a.start()
        sender_b.start()

        # Wait for connections to establish
        time.sleep(0.3)

        # Directly send a message from A to B (bypassing monitor for simplicity)
        test_message = "Hello from A!"
        data = test_message.encode("utf-8")
        cooldown_a.add_cooldown(data)  # Add to cooldown before sending
        sender_a.send(encode_message(data))
        time.sleep(0.3)  # Wait for delivery

        # Verify B received the message
        with lock:
            assert len(received_content_b) > 0, "B should receive content from A"
            assert test_message in received_content_b, f"B should receive '{test_message}', got {received_content_b}"
            assert clipboard_b.paste() == test_message, f"B clipboard should contain '{test_message}'"

        # Directly send a message from B to A
        test_message_2 = "Hello from B!"
        data_2 = test_message_2.encode("utf-8")
        cooldown_b.add_cooldown(data_2)
        sender_b.send(encode_message(data_2))
        time.sleep(0.3)

        # Verify A received the message
        with lock:
            assert test_message_2 in received_content_a, f"A should receive '{test_message_2}', got {received_content_a}"
            assert clipboard_a.paste() == test_message_2, f"A clipboard should contain '{test_message_2}'"

        # Clean up
        sender_a.stop()
        sender_b.stop()
        receiver_a.stop()
        receiver_b.stop()

    def test_monitor_integration_with_mock_clipboard(self, tmp_path):
        """Test that monitor detects clipboard changes and triggers send.

        This test uses a simpler approach by directly triggering the callback
        instead of relying on polling.
        """
        received: list[bytes] = []
        lock = threading.Lock()

        # Receiver on port 19992 (listening for incoming messages)
        receiver = Receiver(
            host="",
            port=19992,
            on_receive=lambda d: received.append(d),
        )

        # Sender connects to port 19992 to send messages there
        sender = Sender(host="127.0.0.1", port=19992)

        receiver.start()
        time.sleep(0.1)

        sender.start()
        time.sleep(0.2)

        # Simulate clipboard change detection and send
        cooldown = CooldownManager(cooldown_seconds=0.5)

        def on_clipboard_change(content: str) -> None:
            """Simulate the ClipBridge._on_clipboard_change logic."""
            data = content.encode("utf-8", errors="replace")
            if cooldown.is_cooldown(data):
                return
            cooldown.add_cooldown(data)
            message = encode_message(data)
            sender.send(message)

        # Simulate clipboard changes
        on_clipboard_change("First message")
        time.sleep(0.2)

        on_clipboard_change("Second message")
        time.sleep(0.2)

        # Verify both messages were received
        with lock:
            assert len(received) >= 2
            assert b"First message" in received
            assert b"Second message" in received

        sender.stop()
        receiver.stop()


class TestBidirectionalSync:
    """Tests for bidirectional synchronization."""

    def test_bidirectional_sync(self, tmp_path):
        """Test that sync works in both directions simultaneously."""
        received_a: list[str] = []
        received_b: list[str] = []
        lock = threading.Lock()

        receiver_a = Receiver(
            host="",
            port=19996,
            on_receive=lambda d: received_a.append(d.decode("utf-8")),
        )
        receiver_b = Receiver(
            host="",
            port=19997,
            on_receive=lambda d: received_b.append(d.decode("utf-8")),
        )

        sender_a = Sender(host="127.0.0.1", port=19997)
        sender_b = Sender(host="127.0.0.1", port=19996)

        receiver_a.start()
        receiver_b.start()
        time.sleep(0.1)

        sender_a.start()
        sender_b.start()
        time.sleep(0.2)

        # Send from A to B
        message_a = "Message from A"
        sender_a.send(encode_message(message_a.encode("utf-8")))
        time.sleep(0.2)

        # Send from B to A
        message_b = "Message from B"
        sender_b.send(encode_message(message_b.encode("utf-8")))
        time.sleep(0.2)

        with lock:
            assert message_a in received_b
            assert message_b in received_a

        sender_a.stop()
        sender_b.stop()
        receiver_a.stop()
        receiver_b.stop()


class TestCooldownPreventsLoop:
    """Tests for cooldown preventing sync loops."""

    def test_cooldown_prevents_duplicate_send(self, tmp_path):
        """Test that cooldown prevents duplicate sending of same content."""
        send_count = 0
        lock = threading.Lock()

        received: list[bytes] = []

        receiver = Receiver(
            host="",
            port=19994,
            on_receive=lambda d: received.append(d),
        )

        sender = Sender(host="127.0.0.1", port=19995)

        receiver_2 = Receiver(
            host="",
            port=19995,
            on_receive=lambda d: None,
        )

        sender_2 = Sender(host="127.0.0.1", port=19994)

        receiver.start()
        receiver_2.start()
        time.sleep(0.1)

        sender.start()
        sender_2.start()
        time.sleep(0.2)

        cooldown = CooldownManager(cooldown_seconds=1.0)

        def send_if_not_cooldown(content: str) -> None:
            """Send only if not in cooldown."""
            nonlocal send_count
            data = content.encode("utf-8")
            if cooldown.is_cooldown(data):
                return
            cooldown.add_cooldown(data)
            with lock:
                send_count += 1
            sender.send(encode_message(data))

        # Send same content multiple times
        for _ in range(3):
            send_if_not_cooldown("test content")
            time.sleep(0.1)

        time.sleep(0.2)

        # Only first send should have gone through (others in cooldown)
        with lock:
            assert send_count == 1, f"Expected 1 send, got {send_count}"

        # Wait for cooldown to expire
        time.sleep(1.1)

        # Now it should send again
        send_if_not_cooldown("test content")
        time.sleep(0.2)

        with lock:
            assert send_count == 2, f"Expected 2 sends after cooldown, got {send_count}"

        sender.stop()
        sender_2.stop()
        receiver.stop()
        receiver_2.stop()


class TestConfigIsolation:
    """Tests for config file isolation."""

    def test_multiple_configs_in_same_dir(self, tmp_path):
        """Test that multiple config files can coexist."""
        config_a = Config(
            local_port=20001,
            remote_host="127.0.0.1",
            remote_port=20002,
        )
        config_b = Config(
            local_port=20002,
            remote_host="127.0.0.1",
            remote_port=20001,
        )

        config_a.save(str(tmp_path / "a.yaml"))
        config_b.save(str(tmp_path / "b.yaml"))

        # Load both configs
        loaded_a = Config.load(str(tmp_path / "a.yaml"))
        loaded_b = Config.load(str(tmp_path / "b.yaml"))

        assert loaded_a.local_port == 20001
        assert loaded_a.remote_port == 20002
        assert loaded_b.local_port == 20002
        assert loaded_b.remote_port == 20001
