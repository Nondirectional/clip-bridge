"""Device discovery module for Clip Bridge.

Provides data structures and protocol for auto-discovery of peer devices on the local network.
"""

from __future__ import annotations

from dataclasses import dataclass

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
