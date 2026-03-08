"""Main entry point for Clip Bridge.

This module provides the main orchestration class that coordinates
all components (receiver, sender, monitor) and handles signal handling
for graceful shutdown.
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys

import pyperclip

from clip_bridge.config import Config, ConfigError
from clip_bridge.cooldown import CooldownManager
from clip_bridge.discovery import UDPAutoDiscovery, DiscoveryConfig, PeerDevice
from clip_bridge.interactive import InteractiveSetup, find_config
from clip_bridge.monitor import Monitor
from clip_bridge.protocol import encode_message, ProtocolError
from clip_bridge.receiver import Receiver
from clip_bridge.sender import Sender

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ClipBridge:
    """Main orchestration class for clipboard synchronization.

    Coordinates the receiver, sender, and monitor components to provide
    seamless clipboard sharing between machines.

    Attributes:
        _config: Loaded configuration.
        _cooldown: Cooldown manager to prevent sync loops.
        _receiver: TCP server for receiving data.
        _sender: TCP client for sending data.
        _monitor: Clipboard monitor for detecting local changes.
    """

    def __init__(self, config_path: str) -> None:
        """Initialize ClipBridge with configuration.

        Args:
            config_path: Path to the YAML configuration file.

        Raises:
            ConfigError: If configuration cannot be loaded or is invalid.
        """
        self._config = Config.load(config_path)
        self._logger = logging.getLogger(__name__)
        self._running = False

        # Auto-discovery: find peer device before initializing components
        if self._config.auto_discover:
            self._logger.info("[INFO] Auto-discovery enabled")
            discovery_config = DiscoveryConfig(
                timeout=self._config.discovery_timeout,
                broadcast_port=self._config.broadcast_port,
            )
            discovery = UDPAutoDiscovery(discovery_config, self._config.local_port)
            peer = discovery.discover()
            if peer:
                self._config.remote_host = peer.ip
                self._config.remote_port = peer.port
                self._logger.info(
                    f"[INFO] Auto-discovered peer: {peer.ip}:{peer.port}"
                )
            else:
                self._logger.info(
                    "[INFO] No peer discovered, using configured values"
                )

        # Initialize cooldown manager
        self._cooldown = CooldownManager(
            cooldown_seconds=self._config.sync_cooldown
        )

        # Initialize components
        self._receiver = Receiver(
            host="",
            port=self._config.local_port,
            on_receive=self._on_receive,
        )
        self._sender = Sender(
            host=self._config.remote_host,
            port=self._config.remote_port,
        )
        self._monitor = Monitor(
            interval=self._config.poll_interval,
            on_change=self._on_clipboard_change,
        )

        logger.info(f"[INFO] ClipBridge initialized")
        logger.info(f"[INFO] Local port: {self._config.local_port}")
        logger.info(f"[INFO] Remote: {self._config.remote_host}:{self._config.remote_port}")

    def start(self) -> None:
        """Start all components (receiver, sender, monitor)."""
        logger.info("[INFO] Starting ClipBridge...")
        self._receiver.start()
        self._sender.start()
        self._monitor.start()
        logger.info("[INFO] ClipBridge running. Press Ctrl+C to stop.")

    def stop(self) -> None:
        """Stop all components gracefully."""
        logger.info("[INFO] Stopping ClipBridge...")
        self._monitor.stop()
        self._sender.stop()
        self._receiver.stop()
        logger.info("[INFO] ClipBridge stopped")

    def _on_clipboard_change(self, content: str) -> None:
        """Handle local clipboard changes.

        Called by the monitor when the local clipboard content changes.
        Encodes and sends the content to the remote peer if not in cooldown.

        Args:
            content: The new clipboard content.
        """
        # Encode content to bytes
        data = content.encode("utf-8", errors="replace")

        # Check if content is in cooldown (prevents sync loops)
        if self._cooldown.is_cooldown(data):
            logger.debug("[DEBUG] Content in cooldown, not sending")
            return

        # Add to cooldown before sending
        self._cooldown.add_cooldown(data)

        # Encode and send
        try:
            message = encode_message(data)
            self._sender.send(message)
            logger.debug(f"[DEBUG] Sent clipboard content ({len(data)} bytes)")
        except ProtocolError as e:
            logger.warning(f"[WARNING] Failed to encode message: {e}")

    def _on_receive(self, data: bytes) -> None:
        """Handle received data from network.

        Called by the receiver when a complete message is received.
        Decodes the content and updates the local clipboard.

        Args:
            data: Decoded content bytes from the protocol layer.
        """
        # Add to cooldown to prevent immediate re-send
        self._cooldown.add_cooldown(data)

        # Decode to string
        try:
            content = data.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.warning(f"[WARNING] Failed to decode content: {e}")
            return

        # Update clipboard
        try:
            pyperclip.copy(content)
            logger.info(f"[INFO] Clipboard updated ({len(data)} bytes)")

            # Update monitor's last content to prevent detecting this as a change
            self._monitor.update_last_content(content)
        except Exception as e:
            logger.error(f"[ERROR] Failed to update clipboard: {e}")


def main() -> int:
    """Main entry point for Clip Bridge.

    Parses command line arguments, loads configuration, and starts
    the clipboard synchronization service.

    Returns:
        0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        description="Clip Bridge - Cross-platform clipboard sharing tool"
    )
    parser.add_argument(
        "config",
        nargs="?",
        help="Path to configuration file (YAML)",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup wizard",
    )

    args = parser.parse_args()

    # Handle --setup flag
    if args.setup:
        setup = InteractiveSetup()
        try:
            result = setup.run()
            return 0 if result else 1
        except Exception as e:
            logger.error(f"[ERROR] Setup failed: {e}")
            return 1

    # Find or load configuration
    config_path = args.config

    if config_path is None:
        # Try to find a config file
        config_path = find_config(".")
        if config_path is None:
            logger.error(
                "[ERROR] No configuration file found. "
                "Run with --setup to create one, or specify a config file path."
            )
            return 1
        logger.info(f"[INFO] Using configuration: {config_path}")

    # Create ClipBridge instance
    try:
        bridge = ClipBridge(config_path)
    except ConfigError as e:
        logger.error(f"[ERROR] Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"[ERROR] Failed to initialize: {e}")
        return 1

    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle SIGINT and SIGTERM for graceful shutdown."""
        logger.info(f"[INFO] Received signal {signum}, shutting down...")
        bridge.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bridge
    try:
        bridge.start()

        # Keep main thread alive
        signal.pause()
    except KeyboardInterrupt:
        logger.info("[INFO] Interrupted by user")
        bridge.stop()
    except Exception as e:
        logger.error(f"[ERROR] Unexpected error: {e}")
        bridge.stop()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
