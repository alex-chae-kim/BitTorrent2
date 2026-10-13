"""Parsing of ``Common.cfg`` and ``PeerInfo.cfg``.

Responsibility
--------------
Turn the two plain-text config files in the working directory into typed,
validated objects, and answer the one ordering question the startup sequence
needs: which peers come *before* me in ``PeerInfo.cfg``.

This module must NOT:
  * open sockets or do any networking;
  * touch the shared data file or the ``peer_[ID]/`` directories;
  * import connection.py, scheduler.py or peerProcess.py.

"""

# Owner: Person A

from __future__ import annotations

from dataclasses import dataclass

#: Keys expected in Common.cfg, mapped to the CommonConfig field they fill.
#: Order here is the canonical order of the file, but parsing must not depend
#: on the order in which keys appear.
COMMON_KEYS: dict[str, str] = {
    "NumberOfPreferredNeighbors": "num_preferred",
    "UnchokingInterval": "unchoking_interval",
    "OptimisticUnchokingInterval": "optimistic_interval",
    "FileName": "file_name",
    "FileSize": "file_size",
    "PieceSize": "piece_size",
}

#: Number of whitespace-separated fields on a PeerInfo.cfg line.
PEER_INFO_FIELDS = 4


class ConfigError(ValueError):
    """Raised for a missing file, an unknown key, or an unparsable line."""


@dataclass(frozen=True)
class CommonConfig:
    """The contents of ``Common.cfg``.

    Attributes
    ----------
    num_preferred:
        ``k`` -- how many preferred neighbours to unchoke each interval.
    unchoking_interval:
        ``p`` -- seconds between preferred-neighbour recalculations.
    optimistic_interval:
        ``m`` -- seconds between optimistic-unchoke recalculations.
    file_name:
        Base name of the shared file (no directory component).
    file_size:
        Total size in bytes.
    piece_size:
        Size of every piece except possibly the last.
    """

    num_preferred: int
    unchoking_interval: int
    optimistic_interval: int
    file_name: str
    file_size: int
    piece_size: int

    @property
    def num_pieces(self) -> int:
        """``ceil(file_size / piece_size)``.

        The last piece is short whenever ``file_size % piece_size != 0``; see
        :meth:`piece_manager.PieceManager.piece_length`.
        """
        raise NotImplementedError


@dataclass(frozen=True)
class PeerInfo:
    """One line of ``PeerInfo.cfg``."""

    peer_id: int
    host: str
    port: int
    has_file: bool


def load_common(path: str) -> CommonConfig:
    """Parse ``Common.cfg`` at *path*.

    Each non-empty line is ``Key Value``. Unknown keys, duplicate keys,
    missing keys, and non-integer values for the integer fields are all
    :class:`ConfigError`.

    Returns
    -------
    CommonConfig
        Fully populated; no field is left to a default.
    """
    raise NotImplementedError


def load_peer_info(path: str) -> list[PeerInfo]:
    """Parse ``PeerInfo.cfg`` at *path*, preserving file order.

    File order is significant: it is the start order of the peers and it
    defines "earlier peer" for :func:`peers_before`.

    Each non-empty line is ``[peerID] [host] [port] [hasFile]`` where
    ``hasFile`` is exactly ``0`` or ``1``. A duplicate peer ID is a
    :class:`ConfigError`.
    """
    raise NotImplementedError


def peers_before(peers: list[PeerInfo], my_id: int) -> list[PeerInfo]:
    """Return the entries that appear before *my_id* in *peers*.

    This peer dials each of these on startup; every later peer dials this
    peer, so the result is a fully connected mesh.

    Raises
    ------
    ConfigError
        If *my_id* does not appear in *peers* at all.
    """
    raise NotImplementedError
