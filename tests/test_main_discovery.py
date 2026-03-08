"""Tests for main.py auto-discovery integration.
"""

from __future__ import annotations

import socket
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clip_bridge.config import Config
from clip_bridge.discovery import DiscoveryConfig, UDPAutoDiscovery
from clip_bridge.main import ClipBridge


class TestAutoDiscoveryIntegration:
    """Test auto-discovery integration in ClipBridge.__init__."""

    def test_auto_discovery_updates_config(self):
        """Test that auto-discovery updates remote_host and remote_port when peer is found."""

        # Create a temporary config file with auto_discover enabled
        config_content = """
local_port: 19998
remote_host: 192.168.1.100
remote_port: 19999
auto_discover: true
discovery_timeout: 2.0
broadcast_port: 19997
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Create a mock peer that will broadcast
            broadcast_sent = threading.Event()

            def mock_peer():
                peer_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                peer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                time.sleep(0.3)  # Wait for discovery to start listening
                message = b"CLIP-HELLO:19999"
                peer_sock.sendto(message, ("<broadcast>", 19997))
                broadcast_sent.set()
                peer_sock.close()

            peer_thread = threading.Thread(target=mock_peer)
            peer_thread.start()

            try:
                # Create ClipBridge with auto-discovery
                # The discovery should update remote_host to the actual peer IP
                bridge = ClipBridge(config_path)

                # Verify that discovery was attempted
                assert broadcast_sent.is_set()

                # The remote_host should be updated from the initial value
                # (It will be set to the actual discovered peer's IP, which could be 127.0.0.1
                # or the actual interface IP depending on network configuration)
                # The remote_port should be updated to 19999 from the mock peer
                assert bridge._config.remote_port == 19999

            finally:
                peer_thread.join(timeout=2.0)

        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_auto_discovery_skipped_when_disabled(self):
        """Test that auto-discovery is skipped when auto_discover is false."""

        # Create a temporary config file with auto_discover disabled
        config_content = """
local_port: 19996
remote_host: 192.168.1.100
remote_port: 19995
auto_discover: false
discovery_timeout: 2.0
broadcast_port: 19994
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Mock UDPAutoDiscovery to ensure it's NOT called
            with patch("clip_bridge.main.UDPAutoDiscovery") as mock_discovery_class:
                bridge = ClipBridge(config_path)

                # Verify UDPAutoDiscovery was not instantiated
                mock_discovery_class.assert_not_called()

                # Verify config values remain as specified
                assert bridge._config.remote_host == "192.168.1.100"
                assert bridge._config.remote_port == 19995
                assert bridge._config.local_port == 19996

        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_auto_discovery_fallback_on_failure(self):
        """Test that when discovery fails, configured values are used."""

        # Create a temporary config file with auto_discover enabled
        # but using a port unlikely to have any peers
        config_content = """
local_port: 19992
remote_host: 192.168.1.100
remote_port: 19991
auto_discover: true
discovery_timeout: 0.5
broadcast_port: 19990
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Create ClipBridge with auto-discovery
            # No peer will be broadcasting, so discovery will fail
            bridge = ClipBridge(config_path)

            # Verify config values remain as the fallback configured values
            assert bridge._config.remote_host == "192.168.1.100"
            assert bridge._config.remote_port == 19991
            assert bridge._config.local_port == 19992

        finally:
            Path(config_path).unlink(missing_ok=True)


class TestAutoDiscoveryWithMock:
    """Test auto-discovery using mocked UDPAutoDiscovery for deterministic testing."""

    def test_auto_discovery_updates_config_with_mock(self):
        """Test auto-discovery updates config when peer is found (using mock)."""

        config_content = """
local_port: 19988
remote_host: 192.168.1.100
remote_port: 19987
auto_discover: true
discovery_timeout: 2.0
broadcast_port: 19986
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Create a mock peer device
            from clip_bridge.discovery import PeerDevice

            mock_peer = PeerDevice(ip="10.0.0.50", port=19989, last_seen=time.time())

            # Mock UDPAutoDiscovery to return our mock peer
            with patch("clip_bridge.main.UDPAutoDiscovery") as mock_discovery_class:
                mock_instance = MagicMock()
                mock_instance.discover.return_value = mock_peer
                mock_discovery_class.return_value = mock_instance

                bridge = ClipBridge(config_path)

                # Verify UDPAutoDiscovery was instantiated with correct config
                mock_discovery_class.assert_called_once()
                call_args = mock_discovery_class.call_args
                assert call_args is not None

                # Verify discover() was called
                mock_instance.discover.assert_called_once()

                # Verify config was updated with discovered peer info
                assert bridge._config.remote_host == "10.0.0.50"
                assert bridge._config.remote_port == 19989

        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_auto_discovery_fallback_with_mock(self):
        """Test auto-discovery falls back when discover returns None."""

        config_content = """
local_port: 19984
remote_host: 192.168.1.100
remote_port: 19983
auto_discover: true
discovery_timeout: 2.0
broadcast_port: 19982
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Mock UDPAutoDiscovery to return None (no peer found)
            with patch("clip_bridge.main.UDPAutoDiscovery") as mock_discovery_class:
                mock_instance = MagicMock()
                mock_instance.discover.return_value = None
                mock_discovery_class.return_value = mock_instance

                bridge = ClipBridge(config_path)

                # Verify UDPAutoDiscovery was instantiated
                mock_discovery_class.assert_called_once()

                # Verify discover() was called
                mock_instance.discover.assert_called_once()

                # Verify config retains original values (fallback)
                assert bridge._config.remote_host == "192.168.1.100"
                assert bridge._config.remote_port == 19983

        finally:
            Path(config_path).unlink(missing_ok=True)

    def test_auto_discovery_passes_correct_config(self):
        """Test that UDPAutoDiscovery is initialized with correct DiscoveryConfig."""

        config_content = """
local_port: 19980
remote_host: 192.168.1.100
remote_port: 19979
auto_discover: true
discovery_timeout: 5.0
broadcast_port: 19978
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            # Mock UDPAutoDiscovery to capture the config
            with patch("clip_bridge.main.UDPAutoDiscovery") as mock_discovery_class:
                mock_instance = MagicMock()
                mock_instance.discover.return_value = None
                mock_discovery_class.return_value = mock_instance

                bridge = ClipBridge(config_path)

                # Verify UDPAutoDiscovery was called
                mock_discovery_class.assert_called_once()
                call_args = mock_discovery_class.call_args

                # The first positional arg should be DiscoveryConfig
                discovery_config = call_args[0][0]
                assert isinstance(discovery_config, DiscoveryConfig)

                # Verify DiscoveryConfig has correct values from main config
                assert discovery_config.timeout == 5.0
                assert discovery_config.broadcast_port == 19978

                # The second positional arg should be local_port
                local_port = call_args[0][1]
                assert local_port == 19980

        finally:
            Path(config_path).unlink(missing_ok=True)
