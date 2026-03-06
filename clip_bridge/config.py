"""Configuration module for Clip Bridge.

This module provides configuration loading and validation for the clipboard
sharing tool.
"""

from dataclasses import asdict, dataclass

import yaml


class ConfigError(Exception):
    """Exception raised for configuration errors."""

    pass


@dataclass
class Config:
    """Configuration for Clip Bridge.

    Attributes:
        local_port: Local listening port (1-65535).
        remote_host: Remote peer IP address or hostname.
        remote_port: Remote peer port (1-65535).
        poll_interval: Clipboard polling interval in seconds.
        sync_cooldown: Anti-loop cooldown time in seconds.
        max_size: Maximum message size in bytes.
    """

    local_port: int
    remote_host: str
    remote_port: int
    poll_interval: float = 0.5
    sync_cooldown: float = 2.0
    max_size: int = 1048576

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate_port(self.local_port, "local_port")
        self._validate_port(self.remote_port, "remote_port")
        self._validate_remote_host()

    @classmethod
    def load(cls: type["Config"], path: str) -> "Config":
        """Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Config: Loaded configuration instance.

        Raises:
            ConfigError: If the file cannot be read, is invalid,
                        or contains invalid values.
        """
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError as e:
            raise ConfigError(f"Configuration file not found: {path}") from e
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in configuration file: {e}") from e
        except OSError as e:
            raise ConfigError(f"Error reading configuration file: {e}") from e

        # Check required fields
        required_fields = ["local_port", "remote_host", "remote_port"]
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            raise ConfigError(
                f"Missing required fields: {', '.join(missing_fields)}"
            )

        try:
            return cls(
                local_port=int(data["local_port"]),
                remote_host=str(data["remote_host"]),
                remote_port=int(data["remote_port"]),
                poll_interval=float(data.get("poll_interval", 0.5)),
                sync_cooldown=float(data.get("sync_cooldown", 2.0)),
                max_size=int(data.get("max_size", 1048576)),
            )
        except (ValueError, TypeError) as e:
            raise ConfigError(f"Invalid value type in configuration: {e}") from e

    def save(self, path: str) -> None:
        """Save configuration to a YAML file.

        Args:
            path: Path to save the YAML configuration file.

        Raises:
            ConfigError: If the file cannot be written.
        """
        try:
            with open(path, "w") as f:
                yaml.dump(asdict(self), f, default_flow_style=False, sort_keys=False)
        except OSError as e:
            raise ConfigError(f"Error writing configuration file: {e}") from e

    def _validate_port(self, value: int, field_name: str) -> None:
        """Validate that a port number is in valid range.

        Args:
            value: The port value to validate.
            field_name: Name of the field for error messages.

        Raises:
            ConfigError: If the port is out of valid range (1-65535).
        """
        if not 1 <= value <= 65535:
            raise ConfigError(
                f"{field_name} must be between 1 and 65535, got {value}"
            )

    def _validate_remote_host(self) -> None:
        """Validate that remote_host is not empty.

        Raises:
            ConfigError: If remote_host is empty or whitespace-only.
        """
        if not self.remote_host or not self.remote_host.strip():
            raise ConfigError("remote_host cannot be empty")
