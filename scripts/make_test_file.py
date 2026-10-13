#!/usr/bin/env python3
"""Generate the shared test file for every seed peer.

Reads ``Common.cfg`` and ``PeerInfo.cfg`` from the working directory, creates
``peer_<ID>/<FileName>`` of exactly ``FileSize`` bytes for each peer with
``hasFile == 1``, and leaves non-seed peers alone -- their copy is
pre-allocated by :class:`piece_manager.PieceManager` at startup.

Usage (from the working directory)::

    python scripts/make_test_file.py                 # all seeds, from configs
    python scripts/make_test_file.py --size 1048576  # smaller file for a
                                                     # quick run
    python scripts/make_test_file.py --peer 1001     # just one peer

The content is deterministic given a seed so ``scripts/verify.sh`` can compare
copies, and incompressible enough that a short read shows up as a mismatch
rather than as more zeroes.
"""

# Owner: Person A

from __future__ import annotations

import argparse

#: Default RNG seed, so two runs of this script produce the same file.
DEFAULT_SEED = 0xB17B0117

#: Write in chunks rather than building FileSize bytes in memory.
CHUNK_SIZE = 1 << 20


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse ``--size``, ``--peer``, ``--seed`` and ``--working-dir``.

    ``--size`` overrides ``FileSize`` from ``Common.cfg`` (handy for a fast
    smoke test); ``--peer`` restricts generation to one peer ID, whether or
    not its ``hasFile`` flag is set.
    """
    raise NotImplementedError


def generate_file(path: str, size: int, seed: int) -> None:
    """Write *size* deterministic pseudo-random bytes to *path*.

    Creates parent directories as needed and overwrites an existing file.
    """
    raise NotImplementedError


def main(argv: list[str]) -> int:
    """Generate a file for every selected seed peer. Returns an exit status."""
    raise NotImplementedError


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
