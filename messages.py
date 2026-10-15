"""Wire-format encoding and decoding.

Responsibility
--------------
The single source of truth for the bytes on the wire: the 32-byte handshake
and the length-prefixed messages after it. Builders return complete, framed
byte strings that a caller can hand straight to ``Connection.send``.

This module must NOT:
  * open sockets, read, or write (it is pure bytes in, bytes out);
  * make protocol decisions (who to choke, what to request);
  * import connection.py, scheduler.py or peerProcess.py.

Frame layout
------------
Handshake (32 bytes, no length prefix)::

    "P2PFILESHARINGPROJ" (18 ASCII bytes) | 10 zero bytes | peer ID (4 bytes)

Every later message::

    length (4 bytes) | type (1 byte) | payload (length - 1 bytes)

``length`` counts the type byte plus the payload and excludes itself. All
integers are 4-byte big-endian (``!I`` / ``int.to_bytes(4, "big")``).
"""

# Owner: Unclaimed

from __future__ import annotations

# --- message types ---------------------------------------------------------
CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6
PIECE = 7

#: Human-readable names, for debug output only -- never for the graded log.
TYPE_NAMES: dict[int, str] = {
    CHOKE: "choke",
    UNCHOKE: "unchoke",
    INTERESTED: "interested",
    NOT_INTERESTED: "not interested",
    HAVE: "have",
    BITFIELD: "bitfield",
    REQUEST: "request",
    PIECE: "piece",
}

#: Types that carry no payload at all.
EMPTY_PAYLOAD_TYPES = frozenset({CHOKE, UNCHOKE, INTERESTED, NOT_INTERESTED})

# --- handshake -------------------------------------------------------------
HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
HANDSHAKE_ZERO_BYTES = 10
HANDSHAKE_LEN = 32

# --- framing ---------------------------------------------------------------
LENGTH_PREFIX_LEN = 4
TYPE_LEN = 1
INDEX_LEN = 4


class ProtocolError(Exception):
    """Raised for a bad handshake header or an undecodable message."""


def build_handshake(peer_id: int) -> bytes:
    """Return the 32-byte handshake for *peer_id*."""
    zero_bytes = b'\x00' * HANDSHAKE_ZERO_BYTES
    peer_id_b = peer_id.to_bytes(INDEX_LEN, byteorder='big')
    return HANDSHAKE_HEADER + zero_bytes + peer_id_b



def parse_handshake(data: bytes) -> int:
    """Return the peer ID carried by a 32-byte handshake.

    Raises
    ------
    ProtocolError
        If *data* is not exactly :data:`HANDSHAKE_LEN` bytes or the header
        does not match :data:`HANDSHAKE_HEADER`. The 10 zero bytes are
        tolerated whatever they contain; the caller is responsible for
        checking the returned ID against the peer it expected.
    """
    if len(data) != HANDSHAKE_LEN:
        raise ProtocolError(f'Received data is not HANDSHAKE_LEN ({HANDSHAKE_LEN}) bytes. Recevied handshake of length {len(data)} bytes.')

    header = data[:len(HANDSHAKE_HEADER)]
    if header != HANDSHAKE_HEADER:
        raise ProtocolError(f'Received data header is wrong. Got {header.decode()} when expected {HANDSHAKE_HEADER.decode()}')

    return int.from_bytes(data[28:32], byteorder='big')


def build_choke() -> bytes:
    """Return a framed ``choke`` message."""
    return frame(CHOKE)


def build_unchoke() -> bytes:
    """Return a framed ``unchoke`` message."""
    return frame(UNCHOKE)


def build_interested() -> bytes:
    """Return a framed ``interested`` message."""
    return frame(INTERESTED)


def build_not_interested() -> bytes:
    """Return a framed ``not interested`` message."""
    return frame(NOT_INTERESTED)


def build_have(index: int) -> bytes:
    """Return a framed ``have`` message for piece *index*."""
    return frame(HAVE, index.to_bytes(INDEX_LEN, 'big'))


def build_bitfield(bitfield_bytes: bytes) -> bytes:
    """Return a framed ``bitfield`` message wrapping *bitfield_bytes*.

    *bitfield_bytes* comes from :meth:`piece_manager.Bitfield.to_bytes`;
    this function does not interpret it. Sent only immediately after the
    handshake. A peer with no pieces may skip the message entirely, so an
    empty payload is legal but so is never sending one.
    """
    return frame(BITFIELD, bitfield_bytes)


def build_request(index: int) -> bytes:
    """Return a framed ``request`` for whole piece *index* (no sub-pieces)."""
    return frame(REQUEST, index.to_bytes(INDEX_LEN, 'big'))


def build_piece(index: int, data: bytes) -> bytes:
    """Return a framed ``piece`` message: index followed by raw *data*.

    *data* must be exactly ``piece_length(index)`` bytes; the short final
    piece is sent short.
    """
    return frame(PIECE, index.to_bytes(INDEX_LEN, 'big') + data)


def frame(msg_type: int, payload: bytes = b"") -> bytes:
    """Prepend the 4-byte length and 1-byte type to *payload*.

    Shared by every builder above; exposed for tests and for any message a
    caller assembles by hand.
    """
    length = TYPE_LEN + len(payload)
    return length.to_bytes(LENGTH_PREFIX_LEN, "big") + bytes([msg_type]) + payload


def parse_payload(msg_type: int, payload: bytes) -> object:
    """Decode *payload* according to *msg_type*.

    Returns
    -------
    ``None``
        for choke / unchoke / interested / not_interested (payload must be
        empty).
    ``int``
        the piece index, for have and request.
    ``bytes``
        the raw bitfield bytes, for bitfield.
    ``tuple[int, bytes]``
        ``(index, data)``, for piece.

    Raises
    ------
    ProtocolError
        On an unknown *msg_type* or a payload of the wrong length.
    """
    if msg_type in EMPTY_PAYLOAD_TYPES:
        if payload:
            raise ProtocolError('choke/unchoke/interested/not_interested message cannot have nonempty payload')
        return None

    if msg_type == HAVE or msg_type == REQUEST:
        if len(payload) != INDEX_LEN:
            raise ProtocolError('have/request payload has to be 4 bytes')
        return int.from_bytes(payload, "big")

    if msg_type == BITFIELD:
        return payload

    if msg_type == PIECE:
        if len(payload) < INDEX_LEN:
            raise ProtocolError('piece payload must have 4 byte index')
        return int.from_bytes(payload[0:INDEX_LEN], 'big'), payload[INDEX_LEN:]

    raise ProtocolError(f'received unrecognizeable message of type {msg_type}')
