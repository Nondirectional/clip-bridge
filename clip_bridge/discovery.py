"""Device discovery module for Clip Bridge.

Provides data structures for auto-discovery of peer devices on the local network.
"""

from __future__ import annotations

from dataclasses import dataclass


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
