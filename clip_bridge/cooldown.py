"""Cooldown manager for preventing clipboard sync loops.

Uses content hashing and timestamps to track recently synchronized content
and prevent immediate re-synchronization.
"""

import hashlib
import time
from collections import OrderedDict
from typing import Final


class CooldownManager:
    """Manages cooldown state for clipboard content to prevent sync loops.

    Tracks content by SHA256 hash with timestamps. Content is considered
    "in cooldown" if it was added within the cooldown period.
    """

    def __init__(
        self,
        cooldown_seconds: float = 2.0,
        max_entries: int = 1000,
    ) -> None:
        """Initialize the cooldown manager.

        Args:
            cooldown_seconds: Time in seconds before content exits cooldown.
            max_entries: Maximum number of entries to track. Oldest is evicted
                when limit is reached.
        """
        self._cooldown_seconds: Final = cooldown_seconds
        self._max_entries: Final = max_entries
        self._entries: OrderedDict[str, float] = OrderedDict()

    def _hash(self, content: bytes) -> str:
        """Compute SHA256 hash of content.

        Args:
            content: The content bytes to hash.

        Returns:
            Hexadecimal string representation of the SHA256 hash.
        """
        return hashlib.sha256(content).hexdigest()

    def add_cooldown(self, content: bytes) -> None:
        """Add content to cooldown list.

        If content already exists, its timestamp is updated to now.
        Oldest entry is evicted if max_entries is reached.

        Args:
            content: The content bytes to track.
        """
        content_hash = self._hash(content)
        current_time = time.time()

        # Remove existing entry if present (will be re-added at end)
        if content_hash in self._entries:
            del self._entries[content_hash]

        # Evict oldest if at capacity
        if len(self._entries) >= self._max_entries:
            self._entries.popitem(last=False)

        # Add entry (newest at end)
        self._entries[content_hash] = current_time

    def is_cooldown(self, content: bytes) -> bool:
        """Check if content is currently in cooldown.

        Automatically removes expired entries during the check.

        Args:
            content: The content bytes to check.

        Returns:
            True if content is in cooldown, False otherwise.
        """
        # Auto-cleanup expired entries
        self._cleanup()

        content_hash = self._hash(content)
        return content_hash in self._entries

    def _cleanup(self) -> None:
        """Remove expired entries from the cooldown list."""
        current_time = time.time()
        cutoff_time = current_time - self._cooldown_seconds

        # Find expired entries (ordered from oldest to newest)
        expired_hashes = [
            hash_value
            for hash_value, timestamp in self._entries.items()
            if timestamp < cutoff_time
        ]

        # Remove expired entries
        for hash_value in expired_hashes:
            del self._entries[hash_value]

    def cleanup(self) -> None:
        """Remove expired entries from the cooldown list.

        Public method for manual cleanup if needed.
        """
        self._cleanup()
