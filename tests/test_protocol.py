"""Tests for the CLIP protocol module."""

import pytest

from clip_bridge.protocol import (
    PREFIX,
    SEPARATOR,
    MAX_MESSAGE_SIZE,
    encode_message,
    decode_message,
    ProtocolError,
)


class TestEncodeMessage:
    """Tests for encode_message function."""

    def test_encode_simple_message(self):
        """Encode simple 'Hello, World!' message."""
        data = b"Hello, World!"
        encoded = encode_message(data)
        expected = PREFIX + b"13" + SEPARATOR + data
        assert encoded == expected

    def test_encode_empty_message(self):
        """Encode empty bytes."""
        data = b""
        encoded = encode_message(data)
        expected = PREFIX + b"0" + SEPARATOR + data
        assert encoded == expected

    def test_encode_unicode(self):
        """Encode unicode content."""
        data = "Hello, 世界!".encode("utf-8")
        encoded = encode_message(data)
        # "Hello, 世界!" encoded in UTF-8 is 14 bytes
        # (7 for ASCII + 6 for the two Chinese characters: 3 bytes each)
        expected = PREFIX + b"14" + SEPARATOR + data
        assert encoded == expected

    def test_encode_message_too_large(self):
        """Raise ProtocolError for message exceeding MAX_MESSAGE_SIZE."""
        data = b"x" * (MAX_MESSAGE_SIZE + 1)
        with pytest.raises(ProtocolError) as exc_info:
            encode_message(data)
        assert "exceeds maximum size" in str(exc_info.value).lower()

    def test_encode_max_size_message(self):
        """Encode message exactly at MAX_MESSAGE_SIZE."""
        data = b"x" * MAX_MESSAGE_SIZE
        encoded = encode_message(data)
        expected = PREFIX + str(MAX_MESSAGE_SIZE).encode() + SEPARATOR + data
        assert encoded == expected


class TestDecodeMessage:
    """Tests for decode_message function."""

    def test_decode_valid_message(self):
        """Decode valid CLIP protocol message."""
        data = b"Hello, World!"
        encoded = PREFIX + b"13" + SEPARATOR + data
        decoded = decode_message(encoded)
        assert decoded == data

    def test_decode_valid_message_with_newlines(self):
        """Decode message containing newlines."""
        data = b"Line 1\nLine 2\nLine 3"
        encoded = PREFIX + b"20" + SEPARATOR + data
        decoded = decode_message(encoded)
        assert decoded == data

    def test_decode_empty_message(self):
        """Decode empty message."""
        data = b""
        encoded = PREFIX + b"0" + SEPARATOR + data
        decoded = decode_message(encoded)
        assert decoded == data

    def test_decode_invalid_prefix(self):
        """Raise ProtocolError for wrong prefix."""
        encoded = b"WRNG" + b"5" + SEPARATOR + b"Hello"
        with pytest.raises(ProtocolError) as exc_info:
            decode_message(encoded)
        assert "prefix" in str(exc_info.value).lower()

    def test_decode_missing_colon(self):
        """Raise ProtocolError for missing colon separator."""
        encoded = PREFIX + b"5" + b"X" + b"Hello"
        with pytest.raises(ProtocolError) as exc_info:
            decode_message(encoded)
        assert "separator" in str(exc_info.value).lower() or "colon" in str(exc_info.value).lower()

    def test_decode_invalid_length(self):
        """Raise ProtocolError for non-numeric length."""
        encoded = PREFIX + b"abc" + SEPARATOR + b"Hello"
        with pytest.raises(ProtocolError) as exc_info:
            decode_message(encoded)
        assert "length" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    def test_decode_length_mismatch(self):
        """Raise ProtocolError for length mismatch."""
        # Claim length is 10 but only provide 5 bytes
        encoded = PREFIX + b"10" + SEPARATOR + b"Hello"
        with pytest.raises(ProtocolError) as exc_info:
            decode_message(encoded)
        assert "length" in str(exc_info.value).lower() or "mismatch" in str(exc_info.value).lower()

    def test_decode_message_too_large(self):
        """Raise ProtocolError for message exceeding MAX_MESSAGE_SIZE."""
        large_length = MAX_MESSAGE_SIZE + 100
        encoded = PREFIX + str(large_length).encode() + SEPARATOR + b"x"
        with pytest.raises(ProtocolError) as exc_info:
            decode_message(encoded)
        assert "exceeds maximum size" in str(exc_info.value).lower() or "too large" in str(exc_info.value).lower()

    def test_decode_max_size_message(self):
        """Decode message exactly at MAX_MESSAGE_SIZE."""
        data = b"x" * MAX_MESSAGE_SIZE
        encoded = PREFIX + str(MAX_MESSAGE_SIZE).encode() + SEPARATOR + data
        decoded = decode_message(encoded)
        assert decoded == data
