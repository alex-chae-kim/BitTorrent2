"""The graded per-peer log file.

Responsibility
--------------
Write ``log_peer_[peerID].log`` in the working directory with exactly the
wording the project spec requires. One method per required line, flushed on
every write.

This module must NOT:
  * invent, reword, or reorder log text -- the format strings below are the
    spec and the grader matches on them;
  * write anything else to the log file (debug output goes to stderr);
  * open sockets or import connection.py, scheduler.py or peerProcess.py.

The timestamp format is ours to choose but must include date, hour, minute and
second; :data:`TIME_FORMAT` fixes that choice for every peer.
"""

# Owner: Person A

from __future__ import annotations

#: strftime format for the ``[Time]`` field: date + hour + minute + second.
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

#: Name of the log file, relative to the working directory.
LOG_FILE_TEMPLATE = "log_peer_{peer_id}.log"

# --- required log lines ----------------------------------------------------
# Exact wording from the spec. Do not edit without checking the spec.
FMT_CONNECT_TO = "{time}: Peer {my_id} makes a connection to Peer {other_id}."
FMT_CONNECTED_FROM = "{time}: Peer {my_id} is connected from Peer {other_id}."
FMT_PREFERRED = "{time}: Peer {my_id} has the preferred neighbors {neighbors}."
FMT_OPTIMISTIC = (
    "{time}: Peer {my_id} has the optimistically unchoked neighbor {other_id}."
)
FMT_UNCHOKED_BY = "{time}: Peer {my_id} is unchoked by {other_id}."
FMT_CHOKED_BY = "{time}: Peer {my_id} is choked by {other_id}."
FMT_HAVE = (
    "{time}: Peer {my_id} received the 'have' message from {other_id} "
    "for the piece {index}."
)
FMT_INTERESTED = (
    "{time}: Peer {my_id} received the 'interested' message from {other_id}."
)
FMT_NOT_INTERESTED = (
    "{time}: Peer {my_id} received the 'not interested' message from {other_id}."
)
FMT_DOWNLOADED = (
    "{time}: Peer {my_id} has downloaded the piece {index} from {other_id}. "
    "Now the number of pieces it has is {count}."
)
FMT_COMPLETE = "{time}: Peer {my_id} has downloaded the complete file."

#: Separator for the preferred-neighbour ID list.
NEIGHBOR_SEPARATOR = ", "


class PeerLogger:
    """Append-only writer for one peer's graded log."""

    def __init__(self, peer_id: int, working_dir: str) -> None:
        """Open ``<working_dir>/log_peer_<peer_id>.log`` for appending.

        Takes a lock for use by every write, so the object is safe to share
        across tasks (and across threads, should the model change).
        """
        raise NotImplementedError

    def _write(self, line: str) -> None:
        """Write *line* plus a newline and flush. Internal."""
        raise NotImplementedError

    @staticmethod
    def _now() -> str:
        """Current local time formatted with :data:`TIME_FORMAT`."""
        raise NotImplementedError

    def log_connect_to(self, other_id: int) -> None:
        """This peer dialled *other_id* successfully."""
        raise NotImplementedError

    def log_connected_from(self, other_id: int) -> None:
        """*other_id* dialled this peer and the handshake succeeded."""
        raise NotImplementedError

    def log_preferred(self, neighbors: list[int]) -> None:
        """New preferred-neighbour set, joined by :data:`NEIGHBOR_SEPARATOR`.

        Called once per unchoking interval, including when the set is
        unchanged. An empty *neighbors* list still logs the line.
        """
        raise NotImplementedError

    def log_optimistic(self, other_id: int) -> None:
        """New optimistically unchoked neighbour.

        Not called when no eligible neighbour exists -- there is no spec line
        for "none".
        """
        raise NotImplementedError

    def log_unchoked_by(self, other_id: int) -> None:
        """Received ``unchoke`` from *other_id*."""
        raise NotImplementedError

    def log_choked_by(self, other_id: int) -> None:
        """Received ``choke`` from *other_id*."""
        raise NotImplementedError

    def log_have(self, other_id: int, index: int) -> None:
        """Received ``have`` from *other_id* for piece *index*."""
        raise NotImplementedError

    def log_interested(self, other_id: int) -> None:
        """Received ``interested`` from *other_id*."""
        raise NotImplementedError

    def log_not_interested(self, other_id: int) -> None:
        """Received ``not interested`` from *other_id*."""
        raise NotImplementedError

    def log_downloaded(self, other_id: int, index: int, count: int) -> None:
        """Finished storing piece *index* from *other_id*.

        *count* is this peer's piece count *after* the write.
        """
        raise NotImplementedError

    def log_complete(self) -> None:
        """This peer now has every piece. Logged exactly once."""
        raise NotImplementedError

    def close(self) -> None:
        """Flush and close the log file. Safe to call twice."""
        raise NotImplementedError


def debug(message: str) -> None:
    """Write *message* to stderr.

    The escape hatch for development output: it must never reach the graded
    log file.
    """
    raise NotImplementedError
