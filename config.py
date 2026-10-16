"""
Parsing of ``Common.cfg`` and ``PeerInfo.cfg``.

Turn the two plain-text config files in the working directory into typed
objects and answer which peers come *before* me in ``PeerInfo.cfg``.
"""

# Owner: Blake Crawford

from __future__ import annotations
from dataclasses import dataclass

#: Keys expected in Common.cfg, mapped to the CommonConfig field they fill.
COMMON_KEYS: dict[str, str] = {
    "NumberOfPreferredNeighbors": "num_preferred",
    "UnchokingInterval": "unchoking_interval",
    "OptimisticUnchokingInterval": "optimistic_interval",
    "FileName": "file_name",
    "FileSize": "file_size",
    "PieceSize": "piece_size",
}

#Keys expected in PeerInfo.cfg, mapped to the PeerInfo field they fill.
PEER_INFO_KEYS: dict[int, str] = {
    0: "peer_id",
    1: "host",
    2: "port",
    3: "has_file"
}


class ConfigError(ValueError):
    """Raised when a config file is missing or invalid."""


@dataclass(frozen=True)
class CommonConfig:

    num_preferred: int
    unchoking_interval: int
    optimistic_interval: int
    file_name: str
    file_size: int
    piece_size: int

    @property
    def num_pieces(self) -> int:
        """
        Returns number of pieces in the file.
        """
        return (self.file_size + self.piece_size - 1) // self.piece_size


@dataclass(frozen=True)
class PeerInfo:

    peer_id: int
    host: str
    port: int
    has_file: bool


def load_common(path: str = "Common.cfg") -> CommonConfig:
    """
    Load and validate a CommonConfig from the given file.
    """

    values: dict[str, int | str] = {}

    try:
        config = open(path, "r", encoding="utf-8")
    except OSError as err:
        raise ConfigError(f"Cannot read {path}: {err}")

    with config:
        for line in config:
            stripped = line.strip()
            if not stripped:
                continue

            field_name, raw_value = stripped.split(maxsplit=1)
            field_name = COMMON_KEYS[field_name]
            
            if field_name == "file_name":
                values[field_name] = raw_value
                continue

            values[field_name] = int(raw_value)

    # CommonConfig being a @dataclass, a constructor is generated expecting **values
    return CommonConfig(**values)


def load_peer_info(path: str = "PeerInfo.cfg") -> list[PeerInfo]:
    """
    Load and validate a PeerInfo from the given file.
    """
    peers: list[PeerInfo] = []

    try:
        config = open(path, "r", encoding="utf-8")
    except OSError as err:
        raise ConfigError(f"Cannot read {path}: {err}")

    with config:
        for line in config:
            stripped = line.strip()
            if not stripped:
                continue

            values: dict[str, str | int] = {}

            for i, raw_value in enumerate(stripped.split(maxsplit=3)):
                # Map value from the position in the line, using PEER_INFO_KEYS
                if i == 0 or i== 2:
                    values[PEER_INFO_KEYS[i]] = int(raw_value)
                elif i == 1:
                    values[PEER_INFO_KEYS[i]] = raw_value
                elif i == 3:
                    values[PEER_INFO_KEYS[i]] = raw_value == "1"

            peers.append(PeerInfo(**values))

    return peers


def peers_before(peers: list[PeerInfo], my_id: int) -> list[PeerInfo]:
    """
    Return the entries that appear before *my_id* in *peers*.
    """
    for i in range(len(peers)):
        peer = peers[i]
        if peer.peer_id == my_id:
            return peers[0:i]

    raise ConfigError(f"Peer ID {my_id} not found in peer list")
