"""Tests for config module."""

from pathlib import Path

import pytest

from clip_bridge.config import Config, ConfigError


class TestConfigLoad:
    """Tests for Config.load() method."""

    def test_config_load_valid_file(self, tmp_path):
        """Load valid config and verify all fields."""
        config_file = tmp_path / "valid.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
poll_interval: 0.5
sync_cooldown: 2.0
max_size: 1048576
""")

        config = Config.load(str(config_file))

        assert config.local_port == 9999
        assert config.remote_host == "192.168.1.100"
        assert config.remote_port == 9998
        assert config.poll_interval == 0.5
        assert config.sync_cooldown == 2.0
        assert config.max_size == 1048576

    def test_config_missing_required_field_local_port(self, tmp_path):
        """Raise ConfigError when local_port is missing."""
        config_file = tmp_path / "missing_local_port.yaml"
        config_file.write_text("""
remote_host: 192.168.1.100
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "local_port" in str(exc_info.value)

    def test_config_missing_required_field_remote_host(self, tmp_path):
        """Raise ConfigError when remote_host is missing."""
        config_file = tmp_path / "missing_remote_host.yaml"
        config_file.write_text("""
local_port: 9999
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_host" in str(exc_info.value)

    def test_config_missing_required_field_remote_port(self, tmp_path):
        """Raise ConfigError when remote_port is missing."""
        config_file = tmp_path / "missing_remote_port.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_port" in str(exc_info.value)

    def test_config_invalid_local_port_zero(self, tmp_path):
        """Raise ConfigError for local_port = 0."""
        config_file = tmp_path / "invalid_port_zero.yaml"
        config_file.write_text("""
local_port: 0
remote_host: 192.168.1.100
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "local_port" in str(exc_info.value)
        assert "65535" in str(exc_info.value)

    def test_config_invalid_local_port_negative(self, tmp_path):
        """Raise ConfigError for negative local_port."""
        config_file = tmp_path / "invalid_port_negative.yaml"
        config_file.write_text("""
local_port: -1
remote_host: 192.168.1.100
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "local_port" in str(exc_info.value)

    def test_config_invalid_local_port_too_high(self, tmp_path):
        """Raise ConfigError for local_port > 65535."""
        config_file = tmp_path / "invalid_port_high.yaml"
        config_file.write_text("""
local_port: 65536
remote_host: 192.168.1.100
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "local_port" in str(exc_info.value)

    def test_config_invalid_remote_port_zero(self, tmp_path):
        """Raise ConfigError for remote_port = 0."""
        config_file = tmp_path / "invalid_remote_port_zero.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 0
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_port" in str(exc_info.value)

    def test_config_invalid_remote_port_too_high(self, tmp_path):
        """Raise ConfigError for remote_port > 65535."""
        config_file = tmp_path / "invalid_remote_port_high.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 70000
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_port" in str(exc_info.value)

    def test_config_invalid_remote_host_empty(self, tmp_path):
        """Raise ConfigError for empty remote_host."""
        config_file = tmp_path / "invalid_host_empty.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: ""
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_host" in str(exc_info.value)

    def test_config_invalid_remote_host_whitespace(self, tmp_path):
        """Raise ConfigError for whitespace-only remote_host."""
        config_file = tmp_path / "invalid_host_whitespace.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: "   "
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "remote_host" in str(exc_info.value)

    def test_config_defaults(self, tmp_path):
        """Verify default values for optional fields."""
        config_file = tmp_path / "defaults.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
""")

        config = Config.load(str(config_file))

        assert config.poll_interval == 0.5
        assert config.sync_cooldown == 2.0
        assert config.max_size == 1048576

    def test_config_min_valid_port(self, tmp_path):
        """Accept port = 1 as valid."""
        config_file = tmp_path / "min_port.yaml"
        config_file.write_text("""
local_port: 1
remote_host: 192.168.1.100
remote_port: 1
""")

        config = Config.load(str(config_file))
        assert config.local_port == 1
        assert config.remote_port == 1

    def test_config_max_valid_port(self, tmp_path):
        """Accept port = 65535 as valid."""
        config_file = tmp_path / "max_port.yaml"
        config_file.write_text("""
local_port: 65535
remote_host: 192.168.1.100
remote_port: 65535
""")

        config = Config.load(str(config_file))
        assert config.local_port == 65535
        assert config.remote_port == 65535

    def test_config_invalid_type_local_port_not_a_number(self, tmp_path):
        """Raise ConfigError when local_port is not a valid number."""
        config_file = tmp_path / "invalid_type_port.yaml"
        config_file.write_text("""
local_port: "not_a_number"
remote_host: 192.168.1.100
remote_port: 9998
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "Invalid value type" in str(exc_info.value)

    def test_config_invalid_type_poll_interval_not_a_number(self, tmp_path):
        """Raise ConfigError when poll_interval is not a valid number."""
        config_file = tmp_path / "invalid_type_poll_interval.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
poll_interval: "not_a_float"
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "Invalid value type" in str(exc_info.value)


class TestConfigSave:
    """Tests for Config.save() method."""

    def test_config_save_and_load(self, tmp_path):
        """Save and reload config."""
        config_file = tmp_path / "save_test.yaml"

        # Create original config
        original = Config(
            local_port=7777,
            remote_host="10.0.0.5",
            remote_port=8888,
            poll_interval=1.0,
            sync_cooldown=5.0,
            max_size=2097152,
        )

        # Save to file
        original.save(str(config_file))

        # Load back
        loaded = Config.load(str(config_file))

        assert loaded.local_port == original.local_port
        assert loaded.remote_host == original.remote_host
        assert loaded.remote_port == original.remote_port
        assert loaded.poll_interval == original.poll_interval
        assert loaded.sync_cooldown == original.sync_cooldown
        assert loaded.max_size == original.max_size

    def test_config_save_creates_valid_yaml(self, tmp_path):
        """Verify saved file is valid YAML."""
        config_file = tmp_path / "valid_yaml.yaml"

        config = Config(
            local_port=9999,
            remote_host="192.168.1.100",
            remote_port=9998,
        )

        config.save(str(config_file))

        # Verify file exists and is readable
        content = config_file.read_text()
        assert "local_port: 9999" in content
        assert "remote_host: 192.168.1.100" in content
        assert "remote_port: 9998" in content

        # Verify it can be loaded back
        loaded = Config.load(str(config_file))
        assert loaded.local_port == 9999


class TestAutoDiscoveryConfig:
    """Tests for auto-discovery configuration options."""

    def test_config_load_with_auto_discovery_fields(self, tmp_path):
        """Load config with all auto-discovery fields specified."""
        config_file = tmp_path / "auto_discovery.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
auto_discover: false
discovery_timeout: 5.0
broadcast_port: 9997
""")

        config = Config.load(str(config_file))

        assert config.auto_discover is False
        assert config.discovery_timeout == 5.0
        assert config.broadcast_port == 9997

    def test_config_auto_discover_defaults(self, tmp_path):
        """Verify default values for auto-discovery fields."""
        config_file = tmp_path / "auto_discovery_defaults.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
""")

        config = Config.load(str(config_file))

        assert config.auto_discover is True
        assert config.discovery_timeout == 3.0
        assert config.broadcast_port == 9997

    def test_config_auto_discover_true(self, tmp_path):
        """Load config with auto_discover explicitly set to true."""
        config_file = tmp_path / "auto_discover_true.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
auto_discover: true
""")

        config = Config.load(str(config_file))
        assert config.auto_discover is True

    def test_config_auto_discover_false(self, tmp_path):
        """Load config with auto_discover explicitly set to false."""
        config_file = tmp_path / "auto_discover_false.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
auto_discover: false
""")

        config = Config.load(str(config_file))
        assert config.auto_discover is False

    def test_config_discovery_timeout_custom(self, tmp_path):
        """Load config with custom discovery_timeout."""
        config_file = tmp_path / "discovery_timeout_custom.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
discovery_timeout: 10.0
""")

        config = Config.load(str(config_file))
        assert config.discovery_timeout == 10.0

    def test_config_broadcast_port_custom(self, tmp_path):
        """Load config with custom broadcast_port."""
        config_file = tmp_path / "broadcast_port_custom.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
broadcast_port: 8888
""")

        config = Config.load(str(config_file))
        assert config.broadcast_port == 8888

    def test_config_broadcast_port_validated_in_range(self, tmp_path):
        """Raise ConfigError for broadcast_port out of valid range."""
        config_file = tmp_path / "broadcast_port_invalid.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
broadcast_port: 0
""")

        with pytest.raises(ConfigError) as exc_info:
            Config.load(str(config_file))

        assert "broadcast_port" in str(exc_info.value)

    def test_config_save_includes_auto_discovery_fields(self, tmp_path):
        """Save config includes auto-discovery fields."""
        config_file = tmp_path / "save_auto_discovery.yaml"

        config = Config(
            local_port=9999,
            remote_host="192.168.1.100",
            remote_port=9998,
            auto_discover=False,
            discovery_timeout=5.0,
            broadcast_port=8888,
        )

        config.save(str(config_file))

        # Verify file contains auto-discovery fields
        content = config_file.read_text()
        assert "auto_discover: false" in content
        assert "discovery_timeout: 5.0" in content
        assert "broadcast_port: 8888" in content

        # Verify it can be loaded back
        loaded = Config.load(str(config_file))
        assert loaded.auto_discover is False
        assert loaded.discovery_timeout == 5.0
        assert loaded.broadcast_port == 8888
