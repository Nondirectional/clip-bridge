"""Interactive configuration setup for Clip Bridge.

This module provides an interactive wizard for first-time setup,
allowing users to configure their clipboard bridge without manually
editing YAML files.
"""

from pathlib import Path
from typing import Final

from clip_bridge.config import Config


# Default ports for each machine type (local_port, remote_port)
DEFAULT_PORTS: Final[dict[str, tuple[int, int]]] = {
    "mac": (9999, 9998),
    "ubuntu": (9998, 9999),
}


class InteractiveSetup:
    """Interactive configuration wizard for Clip Bridge.

    This class guides users through the setup process by asking
    questions about their machine type and remote peer configuration.

    Attributes:
        config_dir: Directory where config files will be stored.
        _answers: Predefined answers for testing (bypasses input()).
    """

    def __init__(self, config_dir: str = ".") -> None:
        """Initialize the interactive setup wizard.

        Args:
            config_dir: Directory where config files will be stored.
        """
        self.config_dir = Path(config_dir)
        self._answers: dict[str, str] = {}

    def set_answers(self, answers: dict) -> None:
        """Set predefined answers for testing.

        This allows tests to bypass the interactive input() calls
        by providing predetermined answers.

        Args:
            answers: Dictionary mapping question keys to answers.
                    Expected keys: "machine_type", "remote_ip", "confirm".
        """
        self._answers = answers.copy()

    def run(self) -> str | None:
        """Run the interactive setup wizard.

        Guides the user through:
        1. Selecting machine type (Mac/Ubuntu)
        2. Entering remote IP address
        3. Confirming the configuration
        4. Creating the config file

        Returns:
            Path to the created config file, or None if user cancelled.

        Raises:
            OSError: If unable to write config file.
        """
        print("Clip Bridge Interactive Setup")
        print("-" * 35)

        # Ask for machine type
        machine_type = self._ask_machine_type()
        if not machine_type:
            return None

        # Ask for remote IP
        remote_ip = self._ask_remote_ip()
        if not remote_ip:
            return None

        # Get ports for this machine type
        local_port, remote_port = DEFAULT_PORTS[machine_type]

        # Show summary and confirm
        if not self._confirm_and_proceed(machine_type, remote_ip, local_port, remote_port):
            print("Setup cancelled.")
            return None

        # Create config file
        config_filename = f"{machine_type}.yaml"
        config_path = self.config_dir / config_filename

        config = Config(
            local_port=local_port,
            remote_host=remote_ip,
            remote_port=remote_port,
        )
        config.save(str(config_path))

        print(f"\nConfiguration saved to: {config_path}")
        print(f"\nTo start Clip Bridge, run:")
        print(f"  uv run python -m clip_bridge {config_filename}")

        return str(config_path)

    def _ask_machine_type(self) -> str | None:
        """Ask user for their machine type.

        Returns:
            The machine type ('mac' or 'ubuntu'), or None if invalid.
        """
        print("\nSelect your machine type:")
        print("  1) Mac")
        print("  2) Ubuntu")

        answer = self._ask("Machine type (1/2):", default="1")

        if not answer:
            return None

        # Map numeric choice to machine type
        choice_map = {"1": "mac", "2": "ubuntu"}

        # Allow both numeric and direct input
        machine_type = choice_map.get(answer.strip(), answer.strip().lower())

        if machine_type in DEFAULT_PORTS:
            return machine_type

        print("Invalid choice. Please select 1 for Mac or 2 for Ubuntu.")
        return None

    def _ask_remote_ip(self) -> str | None:
        """Ask user for remote peer IP address.

        Returns:
            The IP address string, or None if invalid.
        """
        answer = self._ask("Remote IP address (e.g., 192.168.1.100):")

        if not answer:
            return None

        ip = answer.strip()
        if ip:
            return ip

        print("IP address cannot be empty.")
        return None

    def _confirm_and_proceed(
        self, machine_type: str, remote_ip: str, local_port: int, remote_port: int
    ) -> bool:
        """Show configuration summary and ask for confirmation.

        Args:
            machine_type: The user's machine type.
            remote_ip: The remote peer's IP address.
            local_port: The local listening port.
            remote_port: The remote peer's port.

        Returns:
            True if user confirmed, False otherwise.
        """
        print("\nConfiguration Summary:")
        print(f"  Machine type: {machine_type.capitalize()}")
        print(f"  Local port:   {local_port}")
        print(f"  Remote host:  {remote_ip}")
        print(f"  Remote port:  {remote_port}")

        answer = self._ask("\nCreate configuration? (y/N):", default="n")

        return answer and answer.strip().lower() in ("y", "yes")

    def _ask(self, question: str, default: str | None = None) -> str:
        """Ask user a question and get their response.

        In testing mode, returns predefined answers from `_answers`.
        In interactive mode, uses `input()` to prompt the user.

        Args:
            question: The question to ask the user.
            default: Default value if user just presses Enter.

        Returns:
            The user's response, or the default value.
        """
        # Check for predefined answer (for testing)
        # Map questions to answer keys
        question_lower = question.lower()

        if "machine type" in question_lower:
            answer = self._answers.get("machine_type")
        elif "ip address" in question_lower:
            answer = self._answers.get("remote_ip")
        elif "create configuration" in question_lower:
            answer = self._answers.get("confirm")
        else:
            answer = None

        if answer is not None:
            return answer

        # Interactive mode - use input()
        try:
            if default is not None:
                prompt = f"{question} [{default}]: "
            else:
                prompt = f"{question}: "

            response = input(prompt).strip()

            return response if response else default
        except EOFError:
            return default if default is not None else ""


def find_config(config_dir: str = ".") -> str | None:
    """Find existing configuration files in the specified directory.

    Searches for YAML configuration files in the given directory.
    Returns the first matching config file path.

    Args:
        config_dir: Directory to search for config files.

    Returns:
        Path to the found config file, or None if none found.
    """
    config_path = Path(config_dir)

    if not config_path.is_dir():
        return None

    # Look for yaml files
    yaml_files = sorted(config_path.glob("*.yaml"))

    for yaml_file in yaml_files:
        # Try to load it as a valid config
        try:
            Config.load(str(yaml_file))
            return str(yaml_file)
        except Exception:
            # Not a valid config file, skip it
            continue

    return None
