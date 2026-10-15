"""This peer's bitfield and its copy of the shared file.

Responsibility
--------------
Own the on-disk storage in ``peer_[ID]/`` and the record of which pieces this
peer holds. Answer "which of their pieces are interesting to me?" and "how
long is piece i?".

This module must NOT:
  * track which pieces are currently *requested* -- the requested-pieces set
    lives in peerProcess.py, because it is global across neighbours;
  * hold any per-neighbour state (choked/interested flags, download rates);
  * open sockets or import connection.py, scheduler.py or peerProcess.py.

Storage model: one pre-allocated file of ``file_size`` bytes at
``<working_dir>/peer_<peer_id>/<file_name>``. Piece ``i`` lives at byte offset
``i * piece_size`` and is ``piece_length(i)`` bytes long, so writes are plain
seek-and-write with no reassembly pass at the end.
"""

# Owner: Unclaimed

from __future__ import annotations

from config import CommonConfig

#: Bits per bitfield byte. Byte 0 covers pieces 0-7, most significant bit
#: first, so piece i is bit ``7 - (i % 8)`` of byte ``i // 8``.
BITS_PER_BYTE = 8


class Bitfield:
    """A fixed-length bitmap of owned pieces.

    Spare trailing bits in the final byte (when ``num_pieces % 8 != 0``) are
    always zero, both in memory and in :meth:`to_bytes`; a peer that sets one
    is sending a piece index that does not exist.
    """

    def __init__(self, num_pieces: int) -> None:
        """Create an all-zero bitfield covering *num_pieces* pieces."""
        raise NotImplementedError

    def set(self, index: int) -> None:
        """Mark piece *index* as owned. Idempotent.

        Raises
        ------
        IndexError
            If *index* is outside ``range(num_pieces)``.
        """
        raise NotImplementedError

    def has(self, index: int) -> bool:
        """Whether piece *index* is owned.

        Raises
        ------
        IndexError
            If *index* is outside ``range(num_pieces)``.
        """
        raise NotImplementedError

    def count(self) -> int:
        """Number of pieces owned."""
        raise NotImplementedError

    def is_complete(self) -> bool:
        """Whether every piece in ``range(num_pieces)`` is owned."""
        raise NotImplementedError

    def to_bytes(self) -> bytes:
        """Serialise to ``ceil(num_pieces / 8)`` bytes, spare bits zero."""
        raise NotImplementedError

    @classmethod
    def from_bytes(cls, data: bytes, num_pieces: int) -> "Bitfield":
        """Deserialise a received bitfield payload.

        *data* must be exactly ``ceil(num_pieces / 8)`` bytes. Spare trailing
        bits that are set are a protocol violation; treat them as an error
        rather than as owned pieces.

        An empty ``data`` with ``num_pieces == 0`` is the only case where a
        zero-length payload is valid -- a peer with no pieces simply skips the
        bitfield message instead of sending an empty one.
        """
        raise NotImplementedError

    def missing_from(self, other: "Bitfield") -> list[int]:
        """Indices *other* has and ``self`` lacks, ascending.

        An empty result means "not interested in *other*". No rarest-first
        ordering is applied -- the caller picks randomly.
        """
        raise NotImplementedError


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
