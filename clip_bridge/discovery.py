"""Device discovery module for Clip Bridge.

Provides data structures and protocol for auto-discovery of peer devices on the local network.
"""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Broadcast protocol constants
BROADCAST_PREFIX: bytes = b"CLIP-HELLO:"


class DiscoveryError(Exception):
    """Exception raised for discovery protocol violations."""
    pass


def encode_broadcast(port: int) -> bytes:
    """Encode a broadcast message.

    Args:
        port: Local listening port.

    Returns:
        Broadcast message bytes.

    Raises:
        DiscoveryError: If port is invalid.
    """
    if not 1 <= port <= 65535:
        raise DiscoveryError(f"Invalid port: {port}")
    return BROADCAST_PREFIX + str(port).encode()


def decode_broadcast(data: bytes) -> int:
    """Decode a broadcast message.

    Args:
        data: Received broadcast message bytes.

    Returns:
        Peer listening port.

    Raises:
        DiscoveryError: If message format is invalid.
    """
    if not data.startswith(BROADCAST_PREFIX):
        raise DiscoveryError(f"Invalid broadcast prefix: {data[:20]}")

    port_str = data[len(BROADCAST_PREFIX):].decode()
    if not port_str:
        raise DiscoveryError("Empty port")

    try:
        port = int(port_str)
    except ValueError as e:
        raise DiscoveryError(f"Invalid port format: {port_str}") from e

    if not 1 <= port <= 65535:
        raise DiscoveryError(f"Invalid port number: {port}")

    return port


@dataclass
class DiscoveryConfig:
    """Auto-discovery configuration.

    Attributes:
        broadcast_port: Broadcast listening port.
        timeout: Discovery timeout in seconds.
        broadcast_interval: Broadcast interval in seconds.
    """

    broadcast_port: int = 9997
    timeout: float = 3.0
    broadcast_interval: float = 0.5


@dataclass
class PeerDevice:
    """Information about a discovered peer device.

    Attributes:
        ip: Device IP address.
        port: Device listening port.
        last_seen: Last discovery time as Unix timestamp.
    """

    ip: str
    port: int
    last_seen: float


class UDPAutoDiscovery:
    """UDP automatic discovery listener."""

    def __init__(self, config: DiscoveryConfig, local_port: int):
        """Initialize auto discovery.

        Args:
            config: Discovery configuration.
            local_port: Local listening port (used to filter own broadcasts).
        """
        self._config = config
        self._local_port = local_port

    def _broadcast_presence(self) -> None:
        """Broadcast own presence to the network."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        try:
            message = encode_broadcast(self._local_port)
            # Broadcast to network broadcast address
            sock.sendto(message, ("255.255.255.255", self._config.broadcast_port))
            logger.info(f"[INFO] Broadcasted presence on port {self._local_port}")
        finally:
            sock.close()

    def _listen_once(self) -> Optional[PeerDevice]:
        """Listen once for broadcast.

        Returns:
            Discovered device info, or None on timeout.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(1.0)  # 1 second timeout

        try:
            sock.bind(("0.0.0.0", self._config.broadcast_port))
            data, addr = sock.recvfrom(1024)

            # Parse broadcast message
            try:
                port = decode_broadcast(data)
            except DiscoveryError:
                logger.debug(f"Received invalid broadcast from {addr}")
                return None

            # Filter out own broadcast
            if port == self._local_port:
                logger.debug(f"Filtered own broadcast (port {port})")
                return None

            # Log discovered device
            ip = addr[0]
            logger.info(f"[INFO] Discovered peer: {ip}:{port}")
            return PeerDevice(ip=ip, port=port, last_seen=time.time())

        except socket.timeout:
            return None
        finally:
            sock.close()
