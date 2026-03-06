"""Tests for discovery module.
"""

from __future__ import annotations

import time

import pytest

from clip_bridge.discovery import (
    BROADCAST_PREFIX,
    decode_broadcast,
    encode_broadcast,
    DiscoveryConfig,
    DiscoveryError,
    PeerDevice,
)


class TestEncodeBroadcast:
    """Test encode_broadcast function."""

    def test_encode_broadcast(self):
        """Test encoding a broadcast message with port 9999."""
        port = 9999
        result = encode_broadcast(port)

        expected = BROADCAST_PREFIX + b"9999"
        assert result == expected

    def test_encode_broadcast_different_port(self):
        """Test encoding broadcast messages with different ports."""
        for port in [1, 80, 443, 9998, 9999, 65535]:
            result = encode_broadcast(port)
            expected = BROADCAST_PREFIX + str(port).encode()
            assert result == expected

    def test_encode_broadcast_invalid_port_zero(self):
        """Test encoding with port 0 raises DiscoveryError."""
        with pytest.raises(DiscoveryError, match="Invalid port: 0"):
            encode_broadcast(0)

    def test_encode_broadcast_invalid_port_negative(self):
        """Test encoding with negative port raises DiscoveryError."""
        with pytest.raises(DiscoveryError, match="Invalid port: -1"):
            encode_broadcast(-1)

    def test_encode_broadcast_invalid_port_too_large(self):
        """Test encoding with port > 65535 raises DiscoveryError."""
        with pytest.raises(DiscoveryError, match="Invalid port: 65536"):
            encode_broadcast(65536)


class TestDecodeBroadcast:
    """Test decode_broadcast function."""

    def test_decode_broadcast_valid(self):
        """Test decoding a valid broadcast message."""
        data = BROADCAST_PREFIX + b"9999"
        result = decode_broadcast(data)

        assert result == 9999

    def test_decode_broadcast_different_ports(self):
        """Test decoding broadcast messages with different ports."""
        for port in [1, 80, 443, 9998, 9999, 65535]:
            data = BROADCAST_PREFIX + str(port).encode()
            result = decode_broadcast(data)
            assert result == port

    def test_decode_broadcast_invalid_prefix(self):
        """Test decoding message with invalid prefix raises DiscoveryError."""
        with pytest.raises(DiscoveryError, match="Invalid broadcast prefix"):
            decode_broadcast(b"INVALID:9999")

    def test_decode_broadcast_empty_port(self):
        """Test decoding message with empty port raises DiscoveryError."""
        data = BROADCAST_PREFIX
        with pytest.raises(DiscoveryError, match="Empty port"):
            decode_broadcast(data)

    def test_decode_broadcast_invalid_format(self):
        """Test decoding message with non-numeric port raises DiscoveryError."""
        data = BROADCAST_PREFIX + b"abc"
        with pytest.raises(DiscoveryError, match="Invalid port format: abc"):
            decode_broadcast(data)

    def test_decode_broadcast_invalid_port_zero(self):
        """Test decoding message with port 0 raises DiscoveryError."""
        data = BROADCAST_PREFIX + b"0"
        with pytest.raises(DiscoveryError, match="Invalid port number: 0"):
            decode_broadcast(data)

    def test_decode_broadcast_invalid_port_negative(self):
        """Test decoding message with negative port raises DiscoveryError."""
        data = BROADCAST_PREFIX + b"-1"
        with pytest.raises(DiscoveryError, match="Invalid port number: -1"):
            decode_broadcast(data)

    def test_decode_broadcast_invalid_port_too_large(self):
        """Test decoding message with port > 65535 raises DiscoveryError."""
        data = BROADCAST_PREFIX + b"65536"
        with pytest.raises(DiscoveryError, match="Invalid port number: 65536"):
            decode_broadcast(data)

    def test_decode_encode_roundtrip(self):
        """Test encoding and decoding are inverse operations."""
        original_port = 9999
        encoded = encode_broadcast(original_port)
        decoded_port = decode_broadcast(encoded)

        assert decoded_port == original_port


class TestPeerDevice:
    """Test PeerDevice dataclass."""

    def test_peer_device_creation(self):
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

    def test_discovery_config_defaults(self):
        """Test DiscoveryConfig with default values."""
        config = DiscoveryConfig()

        assert config.broadcast_port == 9997
        assert config.timeout == 3.0
        assert config.broadcast_interval == 0.5

    def test_discovery_config_custom(self):
        """Test DiscoveryConfig with custom values."""
        config = DiscoveryConfig(
            broadcast_port=8888,
            timeout=5.0,
            broadcast_interval=1.0,
        )

        assert config.broadcast_port == 8888
        assert config.timeout == 5.0
        assert config.broadcast_interval == 1.0
