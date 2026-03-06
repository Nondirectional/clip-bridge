"""Tests for cooldown module."""

import time

from clip_bridge.cooldown import CooldownManager


class TestCooldownInitially:
    """Tests for initial cooldown state."""

    def test_is_not_cooldown_initially(self):
        """New content not in cooldown."""
        manager = CooldownManager()
        content = b"test content"

        assert not manager.is_cooldown(content), "New content should not be in cooldown"


class TestAddCooldown:
    """Tests for add_cooldown method."""

    def test_add_cooldown(self):
        """After adding, content is in cooldown."""
        manager = CooldownManager(cooldown_seconds=1.0)
        content = b"test content"

        manager.add_cooldown(content)

        assert manager.is_cooldown(content), "Content should be in cooldown after adding"

    def test_add_cooldown_updates_existing(self):
        """Re-adding same content updates timestamp."""
        manager = CooldownManager(cooldown_seconds=1.0)
        content = b"test content"

        # First add
        manager.add_cooldown(content)
        first_timestamp = manager._entries[manager._hash(content)]

        # Wait a bit
        time.sleep(0.1)

        # Re-add
        manager.add_cooldown(content)
        second_timestamp = manager._entries[manager._hash(content)]

        # Timestamp should be updated
        assert second_timestamp > first_timestamp, "Timestamp should be updated on re-add"


class TestCooldownExpires:
    """Tests for cooldown expiration."""

    def test_cooldown_expires(self):
        """Content expires after cooldown period."""
        manager = CooldownManager(cooldown_seconds=0.2)
        content = b"test content"

        manager.add_cooldown(content)
        assert manager.is_cooldown(content), "Content should be in cooldown immediately after adding"

        time.sleep(0.3)
        assert not manager.is_cooldown(content), "Content should expire after cooldown period"


class TestDifferentContent:
    """Tests for different content tracking."""

    def test_different_content_separate_cooldown(self):
        """Different content tracked separately."""
        manager = CooldownManager(cooldown_seconds=1.0)
        content1 = b"first content"
        content2 = b"second content"

        manager.add_cooldown(content1)

        assert manager.is_cooldown(content1), "First content should be in cooldown"
        assert not manager.is_cooldown(content2), "Second content should not be in cooldown"


class TestCleanup:
    """Tests for cleanup method."""

    def test_cleanup_expired(self):
        """cleanup() removes expired entries."""
        manager = CooldownManager(cooldown_seconds=0.2)
        content = b"test content"

        manager.add_cooldown(content)
        content_hash = manager._hash(content)
        assert content_hash in manager._entries, "Content should be in entries"

        time.sleep(0.3)
        manager.cleanup()

        assert content_hash not in manager._entries, "Expired entry should be removed by cleanup"


class TestMaxEntries:
    """Tests for max_entries limit."""

    def test_max_entries(self):
        """Oldest entry evicted when max reached."""
        manager = CooldownManager(cooldown_seconds=1.0, max_entries=3)

        # Add entries up to max
        manager.add_cooldown(b"content1")
        manager.add_cooldown(b"content2")
        manager.add_cooldown(b"content3")

        # All should be in cooldown
        assert manager.is_cooldown(b"content1")
        assert manager.is_cooldown(b"content2")
        assert manager.is_cooldown(b"content3")

        # Add one more, should evict oldest
        manager.add_cooldown(b"content4")

        assert not manager.is_cooldown(b"content1"), "Oldest entry should be evicted"
        assert manager.is_cooldown(b"content2"), "Second entry should still be in cooldown"
        assert manager.is_cooldown(b"content3"), "Third entry should still be in cooldown"
        assert manager.is_cooldown(b"content4"), "New entry should be in cooldown"


class TestHash:
    """Tests for _hash method."""

    def test_hash_same_content_same_hash(self):
        """Same content produces same hash."""
        manager = CooldownManager()
        content = b"test content"

        hash1 = manager._hash(content)
        hash2 = manager._hash(content)

        assert hash1 == hash2, "Same content should produce same hash"

    def test_hash_different_content_different_hash(self):
        """Different content produces different hash."""
        manager = CooldownManager()

        hash1 = manager._hash(b"content1")
        hash2 = manager._hash(b"content2")

        assert hash1 != hash2, "Different content should produce different hash"

    def test_hash_empty_content(self):
        """Empty content should produce valid hash."""
        manager = CooldownManager()

        hash_value = manager._hash(b"")

        assert isinstance(hash_value, str), "Hash should be a string"
        assert len(hash_value) > 0, "Hash should not be empty"


class TestAutoCleanup:
    """Tests for automatic cleanup on is_cooldown check."""

    def test_is_cooldown_auto_cleanup(self):
        """is_cooldown removes expired entries automatically."""
        manager = CooldownManager(cooldown_seconds=0.2)
        content = b"test content"

        manager.add_cooldown(content)
        content_hash = manager._hash(content)
        assert content_hash in manager._entries, "Content should be in entries"

        time.sleep(0.3)

        # is_cooldown should trigger cleanup
        result = manager.is_cooldown(content)

        assert not result, "Content should not be in cooldown after expiration"
        assert content_hash not in manager._entries, "Expired entry should be removed by auto cleanup"
