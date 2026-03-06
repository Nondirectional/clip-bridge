"""
Device discovery module for Clip Bridge.

Provides data structures for auto-discovery of peer devices on the local network.
"""

from dataclasses import dataclass


@dataclass
class DiscoveryConfig:
    """Auto-discovery configuration."""

    broadcast_port: int = 9997  # Broadcast listening port
    timeout: float = 3.0  # Discovery timeout (seconds)
    broadcast_interval: float = 0.5  # Broadcast interval (seconds)


@dataclass
class PeerDevice:
    """Information about a discovered peer device."""

    ip: str  # Device IP address
    port: int  # Device listening port
    last_seen: float  # Last discovery time (Unix timestamp)
