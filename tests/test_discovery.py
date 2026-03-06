"""
Tests for discovery module.
"""

import time

import pytest

from clip_bridge.discovery import DiscoveryConfig, PeerDevice


class TestPeerDevice:
    """Test PeerDevice dataclass."""

    def test_peer_device_creation(self) -> None:
        """Test creating a PeerDevice with all fields."""
        ip = "192.168.1.100"
        port = 9999
        last_seen = time.time()

        peer = PeerDevice(ip=ip, port=port, last_seen=last_seen)

        assert peer.ip == ip
        assert peer.port == port
        assert peer.last_seen == last_seen


class TestDiscoveryConfig:
    """Test DiscoveryConfig dataclass."""

    def test_discovery_config_defaults(self) -> None:
        """Test DiscoveryConfig with default values."""
        config = DiscoveryConfig()

        assert config.broadcast_port == 9997
        assert config.timeout == 3.0
        assert config.broadcast_interval == 0.5

    def test_discovery_config_custom(self) -> None:
        """Test DiscoveryConfig with custom values."""
        config = DiscoveryConfig(
            broadcast_port=8888,
            timeout=5.0,
            broadcast_interval=1.0,
        )

        assert config.broadcast_port == 8888
        assert config.timeout == 5.0
        assert config.broadcast_interval == 1.0
