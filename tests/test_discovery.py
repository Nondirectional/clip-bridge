"""Tests for discovery module.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from clip_bridge.discovery import (
    BROADCAST_PREFIX,
    decode_broadcast,
    encode_broadcast,
    DiscoveryConfig,
    DiscoveryError,
    PeerDevice,
    UDPAutoDiscovery,
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


class TestUDPAutoDiscovery:
    """Test UDPAutoDiscovery class."""

    def test_listener_receives_broadcast(self):
        """Test listener receives and decodes a valid broadcast."""
        config = DiscoveryConfig(broadcast_port=19997)
        listener = UDPAutoDiscovery(config, local_port=9998)

        # Create a sender socket to broadcast
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sender.settimeout(1.0)

        peer_result = []
        listen_done = threading.Event()

        def listen_thread():
            peer = listener._listen_once()
            peer_result.append(peer)
            listen_done.set()

        try:
            # Start listening thread first
            listener_thread = threading.Thread(target=listen_thread)
            listener_thread.start()

            # Small delay to ensure listener is bound
            time.sleep(0.1)

            # Send broadcast
            message = encode_broadcast(9999)
            sender.sendto(message, ("<broadcast>", 19997))

            # Wait for listen to complete
            listen_done.wait(timeout=2.0)
            listener_thread.join(timeout=1.0)

            peer = peer_result[0] if peer_result else None
            assert peer is not None
            assert peer.port == 9999
            # IP can be any valid address depending on network configuration
            assert peer.ip is not None and len(peer.ip) > 0
            assert peer.last_seen > 0

        finally:
            sender.close()

    def test_listener_filters_invalid_messages(self):
        """Test listener filters out messages with invalid format."""
        config = DiscoveryConfig(broadcast_port=19998)
        listener = UDPAutoDiscovery(config, local_port=9999)

        # Create a sender socket
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sender.settimeout(1.0)

        peer_result = []
        listen_done = threading.Event()

        def listen_thread():
            peer = listener._listen_once()
            peer_result.append(peer)
            listen_done.set()

        try:
            # Start listening thread first
            listener_thread = threading.Thread(target=listen_thread)
            listener_thread.start()

            # Small delay to ensure listener is bound
            time.sleep(0.1)

            # Send invalid broadcast (wrong prefix)
            sender.sendto(b"INVALID:9999", ("<broadcast>", 19998))

            # Wait for listen to complete
            listen_done.wait(timeout=2.0)
            listener_thread.join(timeout=1.0)

            peer = peer_result[0] if peer_result else None
            # Should return None (invalid message filtered)
            assert peer is None

        finally:
            sender.close()

    def test_listener_filters_own_broadcast(self):
        """Test listener filters out broadcasts from itself (same port)."""
        config = DiscoveryConfig(broadcast_port=19999)
        # Local port is 9999, so we should filter broadcasts with port 9999
        listener = UDPAutoDiscovery(config, local_port=9999)

        # Create a sender socket
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sender.settimeout(1.0)

        peer_result = []
        listen_done = threading.Event()

        def listen_thread():
            peer = listener._listen_once()
            peer_result.append(peer)
            listen_done.set()

        try:
            # Start listening thread first
            listener_thread = threading.Thread(target=listen_thread)
            listener_thread.start()

            # Small delay to ensure listener is bound
            time.sleep(0.1)

            # Send broadcast with the same port as local_port
            message = encode_broadcast(9999)
            sender.sendto(message, ("<broadcast>", 19999))

            # Wait for listen to complete
            listen_done.wait(timeout=2.0)
            listener_thread.join(timeout=1.0)

            peer = peer_result[0] if peer_result else None
            # Should return None (own broadcast filtered)
            assert peer is None

        finally:
            sender.close()

    def test_listener_timeout(self):
        """Test that listener returns None when timeout occurs."""
        config = DiscoveryConfig(broadcast_port=19996)
        discovery = UDPAutoDiscovery(config, local_port=9999)

        # 不发送任何广播，应该超时返回 None
        peer = discovery._listen_once()
        assert peer is None

    def test_broadcast_presence(self):
        """Test _broadcast_presence sends correct broadcast message."""
        config = DiscoveryConfig(broadcast_port=19995)
        discovery = UDPAutoDiscovery(config, local_port=19999)

        # Create a listener socket to receive the broadcast
        listener_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener_sock.settimeout(2.0)

        received_data = []
        receive_done = threading.Event()

        def receive_thread():
            try:
                listener_sock.bind(("0.0.0.0", 19995))
                data, _ = listener_sock.recvfrom(1024)
                received_data.append(data)
            except socket.timeout:
                pass
            finally:
                receive_done.set()

        try:
            # Start receiving thread first
            receiver = threading.Thread(target=receive_thread)
            receiver.start()

            # Small delay to ensure listener is bound
            time.sleep(0.1)

            # Broadcast presence
            discovery._broadcast_presence()

            # Wait for receive to complete
            receive_done.wait(timeout=2.0)
            receiver.join(timeout=1.0)

            # Verify broadcast content
            assert len(received_data) == 1
            data = received_data[0]
            assert data == encode_broadcast(19999)

        finally:
            listener_sock.close()


class TestDiscover:
    """Test discover() method - main discovery flow."""

    def test_discover_peer_found(self):
        """Test successful peer discovery."""
        config = DiscoveryConfig(
            broadcast_port=19994,
            timeout=2.0,
            broadcast_interval=0.2,
        )
        discovery = UDPAutoDiscovery(config, local_port=9998)

        # Create a mock peer that broadcasts on port 9999
        broadcast_sent = threading.Event()

        def mock_peer():
            peer_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            peer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Wait a bit then broadcast
            time.sleep(0.3)
            message = encode_broadcast(9999)
            peer_sock.sendto(message, ("<broadcast>", 19994))
            broadcast_sent.set()
            peer_sock.close()

        peer_thread = threading.Thread(target=mock_peer)
        peer_thread.start()

        try:
            peer = discovery.discover()
            assert peer is not None
            assert peer.port == 9999
            assert peer.ip is not None and len(peer.ip) > 0
            assert peer.last_seen > 0
            assert broadcast_sent.is_set()
        finally:
            peer_thread.join(timeout=2.0)

    def test_discover_peer_timeout(self):
        """Test discovery timeout when no peer is found."""
        config = DiscoveryConfig(
            broadcast_port=19993,
            timeout=0.5,  # Short timeout for faster test
            broadcast_interval=0.2,
        )
        discovery = UDPAutoDiscovery(config, local_port=9998)

        # No peer broadcasting, should timeout and return None
        peer = discovery.discover()
        assert peer is None

    def test_discover_peer_multiple(self):
        """Test that discovery returns first discovered peer when multiple are present."""
        config = DiscoveryConfig(
            broadcast_port=19992,
            timeout=2.0,
            broadcast_interval=0.2,
        )
        discovery = UDPAutoDiscovery(config, local_port=9998)

        # Track which peer was discovered
        discovered_ports = []
        original_listen_once = discovery._listen_once

        def mock_listen_once():
            peer = original_listen_once()
            if peer:
                discovered_ports.append(peer.port)
            return peer

        discovery._listen_once = mock_listen_once

        # Create multiple mock peers broadcasting at slightly different times
        def mock_peer(port: int, delay: float):
            time.sleep(delay)
            peer_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            peer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            message = encode_broadcast(port)
            peer_sock.sendto(message, ("<broadcast>", 19992))
            peer_sock.close()

        # Start multiple peers with different delays
        threads = []
        for port, delay in [(9999, 0.3), (9990, 0.4), (9980, 0.5)]:
            t = threading.Thread(target=mock_peer, args=(port, delay))
            t.start()
            threads.append(t)

        try:
            peer = discovery.discover()
            assert peer is not None
            # Should return the first peer (port 9999 which broadcasts first)
            assert peer.port == 9999
            # Should only have one discovery
            assert len(discovered_ports) == 1
        finally:
            for t in threads:
                t.join(timeout=2.0)
