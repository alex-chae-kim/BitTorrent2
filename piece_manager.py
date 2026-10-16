"""This peer's bitfield and its copy of the shared file.

Storage model: one pre-allocated file of ``file_size`` bytes at
``<working_dir>/peer_<peer_id>/<file_name>``. Piece ``i`` lives at byte offset
``i * piece_size`` and is ``piece_length(i)`` bytes long, so writes are plain
seek-and-write with no reassembly pass at the end.
"""

# Owner: Alex

import math
from __future__ import annotations

from config import CommonConfig

#: Bits per bitfield byte. Byte 0 covers pieces 0-7, most significant bit
#: first, so piece i is bit ``7 - (i % 8)`` of byte ``i // 8``.
BITS_PER_BYTE = 8


class Bitfield:
    """A fixed-length bitmap of owned pieces.

    Spare trailing bits in the final byte (when ``num_pieces % 8 != 0``) are
    always zero, both in memory and in :meth:`to_bytes`
    """

    def __init__(self, num_pieces: int) -> None:
        """Create an all-zero bitfield covering *num_pieces* pieces."""
        self.num_pieces = num_pieces
        self._bytes = bytearray(math.ceil(num_pieces / BITS_PER_BYTE))

    def _locate(self, index: int) -> tuple[int, int]:
        """Byte position and bit mask of piece *index*"""
        if not 0 <= index < self.num_pieces:
            raise IndexError(
                f"piece index {index} outside range({self.num_pieces})"
            )
        return index // BITS_PER_BYTE, 0x80 >> (index % BITS_PER_BYTE)

    def set(self, index: int) -> None:
        """Mark piece *index* as owned.
        """
        pos, mask = self._locate(index)
        self._bytes[pos] |= mask

    def has(self, index: int) -> bool:
        """Whether piece *index* is owned.
        """
        pos, mask = self._locate(index)
        return bool(self._bytes[pos] & mask)

    def count(self) -> int:
        """Number of pieces owned."""
        return sum(byte.bit_count() for byte in self._bytes)

    def is_complete(self) -> bool:
        """Whether every piece in ``range(num_pieces)`` is owned."""
        return self.count() == self.num_pieces

    def to_bytes(self) -> bytes:
        """Serialise to ``ceil(num_pieces / 8)`` bytes, spare bits zero."""
        return bytes(self._bytes)

    @classmethod
    def from_bytes(cls, data: bytes, num_pieces: int) -> "Bitfield":
        """Deserialise a received bitfield payload."""
        bitfield = cls(num_pieces)
        if len(data) != len(bitfield._bytes):
            raise ValueError(
                f"bitfield is {len(data)} bytes, expected "
                f"{len(bitfield._bytes)} for {num_pieces} pieces"
            )
        spare_bits = len(data) * BITS_PER_BYTE - num_pieces
        if data and data[-1] & ((1 << spare_bits) - 1):
            raise ValueError("bitfield sets a spare trailing bit")
        bitfield._bytes[:] = data
        return bitfield

    def missing_from(self, other: "Bitfield") -> list[int]:
        """Indices *other* has and ``self`` lacks, ascending.

        An empty result means "not interested in *other*".
        """
        return [
            i for i in range(self.num_pieces) if other.has(i) and not self.has(i)
        ]


class PieceManager:
    """This peer's pieces plus the file they are stored in."""

    def __init__(
        self,
        config: CommonConfig,
        peer_id: int,
        working_dir: str,
        has_file: bool,
    ) -> None:
        """Create ``peer_<peer_id>/`` and open the data file.

        Parameters
        ----------
        config:
            Supplies ``file_name``, ``file_size``, ``piece_size`` and
            ``num_pieces``.
        has_file:
            ``True`` for a seed: the file must already exist in
            ``peer_<peer_id>/`` at the full ``file_size`` (see
            ``scripts/make_test_file.py``) and the bitfield starts complete.
            ``False``: pre-allocate a sparse file of ``file_size`` zero bytes
            and start with an empty bitfield.
        """
        raise NotImplementedError

    @property
    def bitfield(self) -> Bitfield:
        """This peer's bitfield. Mutated only through :meth:`write_piece`."""
        raise NotImplementedError

    def read_piece(self, index: int) -> bytes:
        """Read piece *index* from disk; ``piece_length(index)`` bytes.

        Raises
        ------
        ValueError
            If the piece is not owned -- never serve a piece we lack.
        """
        raise NotImplementedError

    def write_piece(self, index: int, data: bytes) -> None:
        """Write *data* at offset ``index * piece_size`` and set the bit.

        Flush to disk before returning, so a ``have`` broadcast is never
        ahead of the bytes. Writing a piece already owned is a no-op.

        Raises
        ------
        ValueError
            If ``len(data) != piece_length(index)``.
        """
        raise NotImplementedError

    def has_piece(self, index: int) -> bool:
        """Whether this peer owns piece *index*."""
        raise NotImplementedError

    def count(self) -> int:
        """Number of pieces owned -- the count in the "downloaded" log line."""
        raise NotImplementedError

    def is_complete(self) -> bool:
        """Whether this peer has the whole file."""
        raise NotImplementedError

    def interesting_pieces(self, their_bitfield: Bitfield) -> list[int]:
        """Indices *their_bitfield* has that this peer lacks, ascending.

        Empty means send ``not interested``. Excludes nothing on the basis of
        outstanding requests; peerProcess.py subtracts its requested set.
        """
        raise NotImplementedError

    def piece_length(self, index: int) -> int:
        """Length of piece *index* in bytes.

        ``piece_size`` for every piece except the last, which is
        ``file_size - (num_pieces - 1) * piece_size`` whenever that is
        smaller.

        Raises
        ------
        IndexError
            If *index* is outside ``range(num_pieces)``.
        """
        raise NotImplementedError

    def close(self) -> None:
        """Flush and close the data file. Safe to call twice."""
        raise NotImplementedError
