"""CLIP protocol implementation for clipboard data encoding/decoding.

Message format: CLIP<length>:<content>
- CLIP - 4-byte prefix
- <length> - Content length (decimal string)
- : - Separator
- <content> - Actual content (bytes)

Maximum message size: 1MB (1048576 bytes)
"""

from __future__ import annotations


class ProtocolError(Exception):
    """Exception raised for protocol violations."""

    pass


# Protocol constants
PREFIX: bytes = b"CLIP"
SEPARATOR: bytes = b":"
MAX_MESSAGE_SIZE: int = 1048576  # 1MB


def encode_message(data: bytes) -> bytes:
    """Encode data into CLIP protocol format.

    Args:
        data: Raw bytes to encode.

    Returns:
        Encoded message in CLIP protocol format.

    Raises:
        ProtocolError: If data exceeds MAX_MESSAGE_SIZE.
    """
    if len(data) > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"Data size ({len(data)} bytes) exceeds maximum size "
            f"({MAX_MESSAGE_SIZE} bytes)"
        )

    length_str = str(len(data)).encode()
    return PREFIX + length_str + SEPARATOR + data


def decode_message(data: bytes) -> bytes:
    """Decode CLIP protocol format message.

    Args:
        data: Encoded message in CLIP protocol format.

    Returns:
        Decoded raw bytes content.

    Raises:
        ProtocolError: If message format is invalid or violates protocol rules.
    """
    if not data.startswith(PREFIX):
        raise ProtocolError(
            f"Invalid prefix: expected {PREFIX!r}, got {data[:len(PREFIX)]!r}"
        )

    # Find separator after prefix
    separator_idx = data.find(SEPARATOR, len(PREFIX))
    if separator_idx == -1:
        raise ProtocolError(f"Missing separator '{SEPARATOR.decode()}'")

    # Extract length string
    length_str = data[len(PREFIX):separator_idx]
    if not length_str.isdigit():
        raise ProtocolError(f"Invalid length format: {length_str!r}")

    # Parse length
    length = int(length_str)

    # Validate length against maximum
    if length > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"Message size ({length} bytes) exceeds maximum size "
            f"({MAX_MESSAGE_SIZE} bytes)"
        )

    # Extract content
    content_start = separator_idx + len(SEPARATOR)
    content = data[content_start:]

    # Validate length matches actual content
    if len(content) != length:
        raise ProtocolError(
            f"Length mismatch: header says {length} bytes, "
            f"but got {len(content)} bytes"
        )

    return content
