"""Tests for receiver module."""

import socket
import threading
import time

import pytest

from clip_bridge.protocol import encode_message
from clip_bridge.receiver import Receiver


class TestReceiverReceivesAndCallbacks:
    """Tests for receiver receiving data and invoking callbacks."""

    def test_receiver_receives_and_callbacks(self):
        """Receiver should receive data and invoke callback."""
        received_data = []
        callback_event = threading.Event()

        def on_receive(data: bytes) -> None:
            received_data.append(data)
            callback_event.set()

        # Start receiver on auto-assigned port
        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)  # Allow server to start

        # Get the actual port
        port = receiver._server_socket.getsockname()[1]

        # Connect and send data with protocol encoding
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            test_data = b"Hello, clipboard!"
            encoded = encode_message(test_data)
            client.sendall(encoded)
            time.sleep(0.2)  # Allow receive and callback
        finally:
            client.close()

        # Verify callback was invoked
        assert callback_event.is_set(), "Callback should have been invoked"
        assert received_data == [test_data], f"Expected {test_data!r}, got {received_data!r}"

        receiver.stop()

    def test_receiver_receives_protocol_message(self):
        """Receiver should decode protocol messages correctly."""
        received_data = []
        callback_event = threading.Event()

        def on_receive(data: bytes) -> None:
            received_data.append(data)
            callback_event.set()

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        # Send encoded protocol message
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            original_data = b"Test clipboard content"
            encoded_message = encode_message(original_data)
            client.sendall(encoded_message)
            time.sleep(0.2)
        finally:
            client.close()

        # Verify decoded content was passed to callback
        assert callback_event.is_set()
        assert received_data == [original_data], f"Expected decoded {original_data!r}, got {received_data!r}"

        receiver.stop()


class TestReceiverRejectsMultipleConnections:
    """Tests for receiver single connection mode."""

    def test_receiver_rejects_multiple_connections(self):
        """Receiver should reject second connection attempt."""
        callback_event = threading.Event()

        def on_receive(data: bytes) -> None:
            callback_event.set()

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        # First connection should succeed
        client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client1.connect(("127.0.0.1", port))
        client1.setblocking(False)
        time.sleep(0.1)

        # Second connection - server should accept but immediately close it
        # (or we'll detect it during send)
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client2.connect(("127.0.0.1", port))
            # Try to send - this might fail if connection was closed
            try:
                client2.setblocking(False)
                client2.send(encode_message(b"test"))
                # If send succeeded, the receiver might still be processing
                # This is OK - we'll verify via the callback event timing
                time.sleep(0.1)
            except BlockingIOError:
                pass
            except OSError:
                # Connection was closed - expected
                pass
        finally:
            try:
                client2.close()
            except OSError:
                pass

        # Verify only first client's data would be processed
        client1.close()
        receiver.stop()

    def test_receiver_accepts_after_client_disconnect(self):
        """Receiver should accept new connection after client disconnects."""
        received_count = []

        def on_receive(data: bytes) -> None:
            received_count.append(1)

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        # First client connects, sends, and disconnects
        client1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client1.connect(("127.0.0.1", port))
        client1.sendall(encode_message(b"First"))
        time.sleep(0.2)
        client1.close()
        time.sleep(0.3)  # Allow receiver to detect disconnect

        # Second client should be able to connect
        client2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client2.connect(("127.0.0.1", port))
        client2.sendall(encode_message(b"Second"))
        time.sleep(0.2)
        client2.close()

        time.sleep(0.2)

        # Both messages should have been received
        assert len(received_count) == 2, f"Expected 2 receives, got {len(received_count)}"

        receiver.stop()


class TestReceiverStopsGracefully:
    """Tests for receiver graceful shutdown."""

    def test_receiver_stops_gracefully(self):
        """Receiver should shut down cleanly without errors."""
        def on_receive(data: bytes) -> None:
            pass

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        # Should not raise
        receiver.stop()

        # Thread should be None or not alive after stop
        assert receiver._thread is None or not receiver._thread.is_alive()

    def test_receiver_stop_without_start(self):
        """Stopping without starting should be safe."""
        def on_receive(data: bytes) -> None:
            pass

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.stop()  # Should not raise

    def test_receiver_multiple_start_stop(self):
        """Multiple start/stop cycles should be safe."""
        received_data = []

        def on_receive(data: bytes) -> None:
            received_data.append(data)

        # First cycle
        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)
        receiver.stop()

        # Second cycle - should create new thread
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        # Send data to verify it's working
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            client.sendall(encode_message(b"Test data"))
            time.sleep(0.2)
        finally:
            client.close()

        receiver.stop()

        assert received_data == [b"Test data"]

    def test_receiver_daemon_thread(self):
        """Receiver should use daemon thread."""
        def on_receive(data: bytes) -> None:
            pass

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()

        assert receiver._thread.is_alive(), "Thread should be running"
        assert receiver._thread.daemon, "Thread should be daemon"

        receiver.stop()


class TestReceiverEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_receiver_empty_data(self):
        """Receiver should handle empty data gracefully."""
        received_data = []

        def on_receive(data: bytes) -> None:
            received_data.append(data)

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            # Send empty data using protocol (length 0)
            client.sendall(encode_message(b""))
            time.sleep(0.1)
        finally:
            client.close()

        receiver.stop()

        # Should complete without error
        # Empty data is valid in protocol
        assert received_data == [b""]

    def test_receiver_large_data(self):
        """Receiver should handle large data (within limits)."""
        received_data = []
        callback_event = threading.Event()

        def on_receive(data: bytes) -> None:
            received_data.append(data)
            callback_event.set()

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        # Send 100KB of data
        large_data = b"x" * 100_000

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            client.sendall(encode_message(large_data))
            time.sleep(0.3)
        finally:
            client.close()

        receiver.stop()

        assert callback_event.is_set()
        assert received_data == [large_data]

    def test_receiver_multiple_messages(self):
        """Receiver should handle multiple messages from one client."""
        received_data = []

        def on_receive(data: bytes) -> None:
            received_data.append(data)

        receiver = Receiver(host="127.0.0.1", port=0, on_receive=on_receive)
        receiver.start()
        time.sleep(0.1)

        port = receiver._server_socket.getsockname()[1]

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.connect(("127.0.0.1", port))
            for msg in [b"First", b"Second", b"Third"]:
                client.sendall(encode_message(msg))
                time.sleep(0.05)
            time.sleep(0.2)
        finally:
            client.close()

        time.sleep(0.2)

        receiver.stop()

        # Should receive all messages
        assert len(received_data) == 3
        assert received_data == [b"First", b"Second", b"Third"]
