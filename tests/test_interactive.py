"""Tests for interactive setup module."""

from pathlib import Path

import pytest

from clip_bridge.config import Config
from clip_bridge.interactive import DEFAULT_PORTS, InteractiveSetup, find_config


class TestInteractiveSetup:
    """Tests for InteractiveSetup class."""

    def test_interactive_creates_config_mac(self, tmp_path):
        """Create config file for Mac using set_answers()."""
        setup = InteractiveSetup(config_dir=str(tmp_path))

        # Set predefined answers
        setup.set_answers({
            "machine_type": "mac",
            "remote_ip": "192.168.1.100",
            "confirm": "y",
        })

        # Run setup
        config_path = setup.run()

        # Verify config file exists
        config_file = Path(config_path)
        assert config_file.exists()

        # Verify config values
        config = Config.load(config_path)
        assert config.local_port == 9999
        assert config.remote_port == 9998
        assert config.remote_host == "192.168.1.100"

    def test_interactive_creates_config_ubuntu(self, tmp_path):
        """Create config file for Ubuntu using set_answers()."""
        setup = InteractiveSetup(config_dir=str(tmp_path))

        # Set predefined answers
        setup.set_answers({
            "machine_type": "ubuntu",
            "remote_ip": "192.168.1.50",
            "confirm": "y",
        })

        # Run setup
        config_path = setup.run()

        # Verify config file exists
        config_file = Path(config_path)
        assert config_file.exists()

        # Verify config values
        config = Config.load(config_path)
        assert config.local_port == 9998
        assert config.remote_port == 9999
        assert config.remote_host == "192.168.1.50"

    def test_mac_vs_ubuntu_ports(self, tmp_path):
        """Verify correct ports for each machine type."""
        # Mac should use (local_port=9999, remote_port=9998)
        setup_mac = InteractiveSetup(config_dir=str(tmp_path))
        setup_mac.set_answers({
            "machine_type": "mac",
            "remote_ip": "10.0.0.1",
            "confirm": "y",
        })
        mac_config_path = setup_mac.run()
        mac_config = Config.load(mac_config_path)
        assert mac_config.local_port == 9999
        assert mac_config.remote_port == 9998

        # Ubuntu should use (local_port=9998, remote_port=9999)
        setup_ubuntu = InteractiveSetup(config_dir=str(tmp_path))
        setup_ubuntu.set_answers({
            "machine_type": "ubuntu",
            "remote_ip": "10.0.0.2",
            "confirm": "y",
        })
        ubuntu_config_path = setup_ubuntu.run()
        ubuntu_config = Config.load(ubuntu_config_path)
        assert ubuntu_config.local_port == 9998
        assert ubuntu_config.remote_port == 9999

    def test_default_ports_constant(self):
        """Verify DEFAULT_PORTS has correct values."""
        assert DEFAULT_PORTS == {
            "mac": (9999, 9998),
            "ubuntu": (9998, 9999),
        }

    def test_interactive_rejects_on_no_confirm(self, tmp_path):
        """Return None when user rejects confirmation."""
        setup = InteractiveSetup(config_dir=str(tmp_path))

        setup.set_answers({
            "machine_type": "mac",
            "remote_ip": "192.168.1.100",
            "confirm": "n",
        })

        result = setup.run()
        assert result is None or not Path(result).exists()

    def test_interactive_case_insensitive_machine_type(self, tmp_path):
        """Accept case-insensitive machine type input."""
        # Test uppercase
        setup = InteractiveSetup(config_dir=str(tmp_path))
        setup.set_answers({
            "machine_type": "MAC",
            "remote_ip": "192.168.1.100",
            "confirm": "y",
        })
        config_path = setup.run()
        config = Config.load(config_path)
        assert config.local_port == 9999
        assert config.remote_port == 9998

    def test_interactive_case_insensitive_confirm(self, tmp_path):
        """Accept case-insensitive confirm input."""
        # Test uppercase Y
        setup = InteractiveSetup(config_dir=str(tmp_path))
        setup.set_answers({
            "machine_type": "ubuntu",
            "remote_ip": "192.168.1.100",
            "confirm": "Y",
        })
        config_path = setup.run()
        assert Path(config_path).exists()


class TestFindConfig:
    """Tests for find_config() function."""

    def test_find_config_existing_file(self, tmp_path):
        """Find existing config file in directory."""
        # Create a config file
        config_file = tmp_path / "mac.yaml"
        config_file.write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
""")

        result = find_config(str(tmp_path))
        assert result is not None
        assert result.endswith("mac.yaml")

    def test_find_config_multiple_files(self, tmp_path):
        """Return first config file when multiple exist."""
        # Create multiple config files
        (tmp_path / "mac.yaml").write_text("""
local_port: 9999
remote_host: 192.168.1.100
remote_port: 9998
""")
        (tmp_path / "ubuntu.yaml").write_text("""
local_port: 9998
remote_host: 192.168.1.50
remote_port: 9999
""")

        result = find_config(str(tmp_path))
        assert result is not None
        # Should return one of them (first found alphabetically)
        assert "mac.yaml" in result or "ubuntu.yaml" in result

    def test_find_config_no_files(self, tmp_path):
        """Return None when no config files exist."""
        result = find_config(str(tmp_path))
        assert result is None

    def test_find_config_ignores_non_yaml(self, tmp_path):
        """Ignore non-yaml files when searching for config."""
        # Create non-yaml files
        (tmp_path / "readme.txt").write_text("not a config")
        (tmp_path / "config.json").write_text('{"port": 1234}')

        result = find_config(str(tmp_path))
        assert result is None

    def test_find_config_current_directory(self):
        """Test find_config with '.' as current directory."""
        # Test in empty temp directory
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            result = find_config(td)
            assert result is None

            # Create a config file
            Path(td, "mac.yaml").write_text("local_port: 9999\nremote_host: 192.168.1.100\nremote_port: 9998\n")

            result = find_config(td)
            assert result is not None
            assert "mac.yaml" in result
