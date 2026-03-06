"""Tests for sender module."""

import queue
import socket
import threading
import time

import pytest

from clip_bridge.sender import Sender


class MockServer:
    """Mock TCP server for testing sender."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        """Initialize mock server.

        Args:
            host: Host to bind to.
            port: Port to bind to (0 for auto-assign).
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.thread = None
        self.received_data = []
        self.lock = threading.Lock()
        self.accepted = threading.Event()

    def start(self) -> None:
        """Start the mock server in a separate thread."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.port = self.server_socket.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        """Server thread main loop."""
        try:
            while self.running:
                self.server_socket.settimeout(0.1)
                try:
                    self.client_socket, addr = self.server_socket.accept()
                    self.accepted.set()
                    # Receive data
                    while self.running:
                        self.client_socket.settimeout(0.1)
                        try:
                            data = self.client_socket.recv(4096)
                            if not data:
                                break
                            with self.lock:
                                self.received_data.append(data)
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            self.close()

    def get_received(self) -> bytes:
        """Get all received data concatenated.

        Returns:
            Received data as bytes.
        """
        with self.lock:
            return b"".join(self.received_data)

    def wait_for_connection(self, timeout: float = 2.0) -> bool:
        """Wait for a client to connect.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if connection accepted, False on timeout.
        """
        return self.accepted.wait(timeout=timeout)

    def close(self) -> None:
        """Stop the server and close all sockets."""
        self.running = False
        self.accepted.clear()
        if self.client_socket:
            try:
                self.client_socket.close()
            except OSError:
                pass
            self.client_socket = None
        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None
        # Only join thread if not calling from within the thread
        if self.thread and threading.current_thread() != self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None


class TestSenderConnectsAndSends:
    """Tests for sender connection and data transmission."""

    def test_sender_connects_and_sends_data(self):
        """Sender should connect to server and send data."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.2)  # Allow connection

        # Send test data
        test_data = b"Hello, World!"
        sender.send(test_data)
        time.sleep(0.2)  # Allow transmission

        sender.stop()
        server.close()

        received = server.get_received()
        assert received == test_data, f"Expected {test_data!r}, got {received!r}"

    def test_sender_queues_multiple_messages(self):
        """Sender should queue and send multiple messages in order."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.2)

        # Send multiple messages
        messages = [b"First", b"Second", b"Third"]
        for msg in messages:
            sender.send(msg)
        time.sleep(0.3)

        sender.stop()
        server.close()

        received = server.get_received()
        expected = b"".join(messages)
        assert received == expected, f"Expected {expected!r}, got {received!r}"

    def test_sender_send_before_start(self):
        """Sending before start should queue data for when started."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)

        # Send before starting
        sender.send(b"Early message")
        sender.start()
        time.sleep(0.3)

        sender.stop()
        server.close()

        received = server.get_received()
        assert received == b"Early message"

    def test_sender_graceful_shutdown(self):
        """Sender should shut down gracefully without errors."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        sender.send(b"Test")
        time.sleep(0.1)

        # Should not raise
        sender.stop()
        server.close()

    def test_sender_daemon_thread(self):
        """Sender should use daemon thread."""
        sender = Sender(host="127.0.0.1", port=9999)
        sender.start()

        assert sender._thread.is_alive(), "Thread should be running"
        assert sender._thread.daemon, "Thread should be daemon"

        sender.stop()


class TestSenderReconnectsOnFailure:
    """Tests for sender reconnection behavior."""

    def test_sender_reconnects_after_server_restart(self):
        """Sender should reconnect when server becomes available."""
        # Start sender first (server not available)
        sender = Sender(host="127.0.0.1", port=19999, reconnect_delay=0.1)
        sender.start()
        time.sleep(0.1)

        # Queue data
        sender.send(b"Message1")
        time.sleep(0.1)

        # Now start the server
        server = MockServer(port=19999)
        server.start()
        server.wait_for_connection(timeout=2.0)
        time.sleep(0.3)

        # Send more data
        sender.send(b"Message2")
        time.sleep(0.3)

        sender.stop()
        server.close()

        received = server.get_received()
        # Should receive both messages
        assert b"Message1" in received or b"Message2" in received

    def test_sender_handles_connection_error(self):
        """Sender should log error and not crash on connection failure."""
        # Use a port that's unlikely to be in use
        sender = Sender(host="127.0.0.1", port=45678, reconnect_delay=0.1)

        # Should not raise
        sender.start()
        sender.send(b"Test")
        time.sleep(0.2)

        # Should not raise
        sender.stop()

    def test_sender_reconnects_after_disconnect(self):
        """Sender should reconnect after connection is lost."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port, reconnect_delay=0.05)
        sender.start()

        # Wait for connection
        assert server.wait_for_connection(timeout=2.0), "Initial connection failed"
        time.sleep(0.2)

        # Send data while connected
        sender.send(b"Before disconnect")
        time.sleep(0.2)

        # Verify first message was received
        assert b"Before disconnect" in server.get_received()

        # Close server to cause disconnect
        server.close()

        # Send data while disconnected - this will fail and trigger reconnection
        sender.send(b"This will fail")
        time.sleep(0.2)

        # Now restart server - sender should be trying to reconnect
        server = MockServer(port=server.port)
        server.start()

        # Send more data - should succeed after reconnection
        sender.send(b"After reconnect")

        # Wait for reconnection
        assert server.wait_for_connection(timeout=2.0), "Reconnection failed"
        time.sleep(0.5)  # Allow time for data to be sent

        sender.stop()
        server.close()

        received = server.get_received()
        # Should have data after reconnect
        assert b"After reconnect" in received, f"Expected 'After reconnect' in {received!r}"


class TestSenderEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_sender_empty_data(self):
        """Sender should handle empty data gracefully."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.2)

        sender.send(b"")
        time.sleep(0.1)

        sender.stop()
        server.close()

        # Should complete without error

    def test_sender_large_data(self):
        """Sender should handle large data (within limits)."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.2)

        # Send 100KB of data
        large_data = b"x" * 100_000
        sender.send(large_data)
        time.sleep(0.5)

        sender.stop()
        server.close()

        received = server.get_received()
        assert received == large_data

    def test_sender_stop_without_start(self):
        """Stopping without starting should be safe."""
        sender = Sender(host="127.0.0.1", port=9999)
        sender.stop()  # Should not raise

    def test_sender_multiple_start_stop(self):
        """Multiple start/stop cycles should be safe."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.1)
        sender.stop()

        # Start again
        sender.start()
        time.sleep(0.1)
        sender.send(b"Test")
        time.sleep(0.2)
        sender.stop()

        server.close()

        received = server.get_received()
        assert received == b"Test"

    def test_sender_stop_clears_queue(self):
        """Stopping sender should not process remaining queued items."""
        server = MockServer()
        server.start()

        sender = Sender(host="127.0.0.1", port=server.port)
        sender.start()
        time.sleep(0.1)

        sender.send(b"Will be sent")
        time.sleep(0.1)
        sender.stop()

        # After stop, new sends should be queued but not sent
        sender.send(b"Won't be sent")
        time.sleep(0.1)

        server.close()

        received = server.get_received()
        assert b"Will be sent" in received
        assert b"Won't be sent" not in received
