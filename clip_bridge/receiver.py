"""TCP receiver for receiving clipboard data from remote peer.

This module provides a threaded TCP server that:
- Accepts a single connection at a time
- Receives data and invokes callbacks
- Gracefully handles shutdown
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Callable, Optional

from clip_bridge.protocol import PREFIX, SEPARATOR, MAX_MESSAGE_SIZE

logger = logging.getLogger(__name__)


class Receiver:
    """TCP server receiver with single connection mode.

    The receiver runs in a separate daemon thread and accepts a single
    client connection. Additional connections are rejected. When data
    is received, the on_receive callback is invoked with the decoded
    content.
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_receive: Callable[[bytes], None],
    ) -> None:
        """Initialize the receiver.

        Args:
            host: Host to bind to.
            port: Port to bind to (0 for auto-assign).
            on_receive: Callback invoked when data is received.
        """
        self._host = host
        self._port = port
        self._on_receive = on_receive

        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        self._buffer: bytearray = bytearray()

    def start(self) -> None:
        """Start the receiver thread.

        Creates and starts a daemon thread that accepts connections.
        Safe to call multiple times - subsequent calls are ignored.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._running = True
            self._buffer = bytearray()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info(f"[INFO] Receiver started on {self._host}:{self._port}")

    def stop(self) -> None:
        """Stop the receiver thread.

        Signals the thread to stop and closes all sockets.
        Safe to call even if the receiver was never started.
        """
        with self._lock:
            self._running = False

        # Close sockets to unblock accept/recv
        self._close_client()
        self._close_server()

        # Wait for thread to finish
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
            logger.info("[INFO] Receiver stopped")

    def _run(self) -> None:
        """Main thread loop.

        Accepts a single connection and handles it. When the client
        disconnects, returns to accepting a new connection.
        """
        # Create and bind server socket
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self._host, self._port))
            self._server_socket.listen(1)
            self._server_socket.settimeout(0.5)  # Allow periodic checking of _running

            # Update port if auto-assigned
            actual_port = self._server_socket.getsockname()[1]
            logger.debug(f"[DEBUG] Receiver listening on port {actual_port}")
        except OSError as e:
            logger.error(f"[ERROR] Failed to bind server socket: {e}")
            self._running = False
            return

        while self._running:
            try:
                # Accept connection (with timeout for checking _running)
                try:
                    client, addr = self._server_socket.accept()
                except socket.timeout:
                    continue

                # Check if we already have a client
                if self._client_socket is not None:
                    logger.info(f"[INFO] Rejecting connection from {addr} (already connected)")
                    try:
                        client.close()
                    except OSError:
                        pass
                    continue

                # Handle the client
                logger.info(f"[INFO] Accepted connection from {addr}")
                self._client_socket = client
                self._buffer = bytearray()  # Clear buffer for new connection
                self._handle_client(client)

            except OSError as e:
                if self._running:
                    logger.debug(f"[DEBUG] Server socket error: {e}")
                break

        # Cleanup
        self._close_server()
        self._close_client()

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle connected client.

        Receives data from the client and invokes the on_receive callback.
        Continues until the client disconnects or an error occurs.

        Args:
            client_socket: The connected client socket.
        """
        try:
            # Set socket timeout to allow checking _running
            client_socket.settimeout(0.5)

            while self._running:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        # Client disconnected
                        logger.debug("[DEBUG] Client disconnected")
                        break

                    # Append to buffer
                    self._buffer.extend(data)

                    # Try to extract complete messages
                    while self._running:
                        message = self._extract_message()
                        if message is None:
                            # No complete message yet
                            break
                        # Invoke callback with decoded content
                        logger.debug(f"[DEBUG] Received {len(message)} bytes")
                        self._on_receive(message)

                except socket.timeout:
                    continue
                except OSError as e:
                    logger.debug(f"[DEBUG] Client socket error: {e}")
                    break

        finally:
            self._close_client()

    def _extract_message(self) -> Optional[bytes]:
        """Extract a complete message from the buffer.

        Returns:
            Decoded message content if a complete message is available,
            None if more data is needed.
        """
        buffer = bytes(self._buffer)

        # Check if we have the prefix
        if not buffer.startswith(PREFIX):
            # Invalid data - clear buffer
            logger.warning("[WARNING] Invalid prefix, clearing buffer")
            self._buffer.clear()
            return None

        # Find separator after prefix
        separator_idx = buffer.find(SEPARATOR, len(PREFIX))
        if separator_idx == -1:
            # Separator not found yet - need more data
            return None

        # Extract length string
        length_str = buffer[len(PREFIX):separator_idx]
        if not length_str.isdigit():
            # Invalid length format
            logger.warning(f"[WARNING] Invalid length format: {length_str!r}")
            self._buffer.clear()
            return None

        # Parse length
        try:
            length = int(length_str)
        except ValueError:
            logger.warning(f"[WARNING] Invalid length value: {length_str!r}")
            self._buffer.clear()
            return None

        # Validate length against maximum
        if length > MAX_MESSAGE_SIZE:
            logger.warning(f"[WARNING] Message size ({length}) exceeds maximum")
            self._buffer.clear()
            return None

        # Calculate total message size
        content_start = separator_idx + len(SEPARATOR)
        total_size = content_start + length

        # Check if we have the complete message
        if len(buffer) < total_size:
            # Need more data
            return None

        # Extract content
        content = buffer[content_start:total_size]

        # Remove the processed message from buffer
        del self._buffer[:total_size]

        return content

    def _close_client(self) -> None:
        """Close the client socket if open."""
        if self._client_socket is not None:
            try:
                self._client_socket.close()
            except OSError:
                pass
            self._client_socket = None

    def _close_server(self) -> None:
        """Close the server socket if open."""
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
