"""Clipboard monitor for detecting changes.

Polls the clipboard at a configurable interval and triggers
a callback when the content changes.
"""

import logging
import threading
import time
from typing import Callable

import pyperclip

logger = logging.getLogger(__name__)


class Monitor:
    """Monitors clipboard for changes using polling.

    Runs in a separate daemon thread and polls pyperclip.paste()
    at the configured interval. When a change is detected, the
    on_change callback is invoked with the new content.
    """

    def __init__(
        self,
        interval: float = 0.5,
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the clipboard monitor.

        Args:
            interval: Polling interval in seconds. Defaults to 0.5.
            on_change: Callback function called when clipboard changes.
                Receives the new content as a string argument.
        """
        self._interval = interval
        self._on_change = on_change
        self._last_content: str = ""
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._initialized = False

    def start(self) -> None:
        """Start the monitor thread.

        Creates and starts a daemon thread that polls the clipboard.
        Does nothing if already started.
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("[INFO] Clipboard monitor started")

    def stop(self) -> None:
        """Stop the monitor thread.

        Signals the polling loop to exit and waits for the thread
        to terminate. Safe to call multiple times.
        """
        if not self._running:
            return

        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

        logger.info("[INFO] Clipboard monitor stopped")

    def update_last_content(self, content: str) -> None:
        """Update the last tracked content.

        This can be used to prevent the monitor from detecting
        content that was just set programmatically (e.g., content
        received from the network).

        Args:
            content: The content to set as the last seen content.
        """
        with self._lock:
            self._last_content = content

    def _run(self) -> None:
        """Main polling loop.

        Continuously polls the clipboard at the configured interval
        and detects changes. Runs until stop() is called.
        """
        while self._running:
            try:
                current_content = pyperclip.paste()

                with self._lock:
                    # On first poll, initialize without triggering callback
                    if not self._initialized:
                        self._last_content = current_content
                        self._initialized = True
                    elif current_content != self._last_content:
                        self._last_content = current_content

                        if self._on_change is not None:
                            try:
                                self._on_change(current_content)
                            except Exception as e:
                                logger.error(
                                    f"[ERROR] Error in on_change callback: {e}"
                                )

            except Exception as e:
                # pyperclip can throw exceptions on some platforms
                # Log but don't crash the monitor
                logger.error(f"[ERROR] Error reading clipboard: {e}")

            # Sleep until next poll, but check _running frequently
            for _ in range(int(self._interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
