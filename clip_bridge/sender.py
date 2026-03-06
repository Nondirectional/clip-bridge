"""TCP sender for sending clipboard data to remote peer.

This module provides a threaded TCP client that:
- Queues outgoing messages asynchronously
- Automatically reconnects on connection failure
- Gracefully handles shutdown
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class Sender:
    """TCP client sender with automatic reconnection.

    The sender runs in a separate daemon thread and maintains a queue
    of outgoing messages. It automatically reconnects to the remote
    peer if the connection is lost.
    """

    def __init__(
        self,
        host: str,
        port: int,
        reconnect_delay: float = 1.0,
    ) -> None:
        """Initialize the sender.

        Args:
            host: Remote host to connect to.
            port: Remote port to connect to.
            reconnect_delay: Delay in seconds between reconnection attempts.
        """
        self._host = host
        self._port = port
        self._reconnect_delay = reconnect_delay

        self._queue: queue.Queue[bytes] = queue.Queue()
        self._socket: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the sender thread.

        Creates and starts a daemon thread that processes outgoing messages.
        Safe to call multiple times - subsequent calls are ignored.
        """
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return

            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info(f"[INFO] Sender started for {self._host}:{self._port}")

    def stop(self) -> None:
        """Stop the sender thread.

        Signals the thread to stop and waits for it to terminate.
        Safe to call even if the sender was never started.
        """
        with self._lock:
            self._running = False

        # Wake up the thread by putting a sentinel
        try:
            self._queue.put_nowait(b"")
        except queue.Full:
            pass

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
            logger.info("[INFO] Sender stopped")

        # Close socket
        self._close_socket()

    def send(self, data: bytes) -> None:
        """Queue data for sending.

        This method is non-blocking. Data is added to a queue and will
        be sent by the sender thread.

        Args:
            data: Bytes data to send.
        """
        try:
            self._queue.put_nowait(data)
        except (queue.Full, AttributeError) as e:
            logger.warning(f"[WARNING] Failed to queue data: {e}")

    def _connect(self) -> bool:
        """Attempt to connect to the remote peer.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self._close_socket()
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(1.0)  # Short timeout for connect
            self._socket.connect((self._host, self._port))
            # Set to blocking mode after connect
            self._socket.settimeout(None)
            logger.info(f"[INFO] Connected to {self._host}:{self._port}")
            return True
        except OSError as e:
            logger.debug(f"[DEBUG] Connection failed: {e}")
            self._close_socket()
            return False

    def _run(self) -> None:
        """Main thread loop.

        Continuously processes queued messages and sends them to the
        remote peer. Handles reconnection if the connection is lost.
        """
        while self._running:
            # Ensure we have a connection
            if self._socket is None:
                if not self._connect():
                    time.sleep(self._reconnect_delay)
                    continue

            # Get data from queue with timeout
            try:
                data = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Check for empty sentinel (stop signal)
            if not data:
                continue

            # Send the data
            if not self._send_data(data):
                # Send failed - re-queue the data and try to reconnect
                try:
                    self._queue.put_nowait(data)
                except queue.Full:
                    logger.warning("[WARNING] Queue full, dropping message")
                continue

    def _send_data(self, data: bytes) -> bool:
        """Send data to the connected socket.

        Args:
            data: Bytes data to send.

        Returns:
            True if send successful, False otherwise.
        """
        if self._socket is None:
            return False

        try:
            self._socket.sendall(data)
            logger.debug(f"[DEBUG] Sent {len(data)} bytes")
            return True
        except OSError as e:
            logger.warning(f"[WARNING] Send failed: {e}")
            self._close_socket()
            return False

    def _close_socket(self) -> None:
        """Close the current socket if open."""
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None
