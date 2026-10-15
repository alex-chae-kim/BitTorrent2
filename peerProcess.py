"""Entry point and shared state for one peer.

Run from the working directory -- the directory holding ``Common.cfg`` and
``PeerInfo.cfg`` -- as::

    python peerProcess.py <peerID>

Responsibility
--------------
Wire everything together and own the state that is global to this peer rather
than to one neighbour: the connections table, the set of piece indices
currently requested from *someone*, the current preferred set, and the
optimistic neighbour. All protocol decisions live here; the modules below
(config, messages, piece_manager, logger, connection, scheduler) stay
unaware of each other's policy.

Concurrency model: asyncio, one event loop. ``PeerProcess.run`` opens an
:class:`asyncio.TaskGroup` (Python 3.11+) holding the listener, one reader
task per connection, and the two timer loops from scheduler.py. Because every
handler runs on that single loop, no locks are needed around the shared state
below -- but every handler must stay non-blocking: file I/O through
:class:`~piece_manager.PieceManager` is the one place that briefly blocks, and
it is deliberately kept to whole-piece reads and writes.

Note
----
If this file grows past roughly 400 lines, split the ``handle_*`` methods out
into ``protocol.py`` and keep only startup, shared state and shutdown here.
"""

# Owner: Unclaimed (integration is shared)

from __future__ import annotations

import asyncio
import random
from typing import Optional

from config import CommonConfig, PeerInfo
from connection import Connection
from logger import PeerLogger
from piece_manager import PieceManager
from scheduler import NeighborSnapshot

#: Interface to listen on. ``PeerInfo.cfg`` gives a host per peer, but that is
#: the address other peers dial; locally we bind every interface so the same
#: config works for multi-host testing.
LISTEN_HOST = "0.0.0.0"

#: Grace period after the last peer completes, so final ``have`` messages are
#: delivered before sockets close.
SHUTDOWN_GRACE = 2.0


class PeerProcess:
    """One running peer: its state, its handlers, its lifecycle."""

    def __init__(self, peer_id: int, working_dir: str = ".") -> None:
        """Set up state from the configs in *working_dir*.

        Loads ``Common.cfg`` and ``PeerInfo.cfg``, finds our own
        :class:`~config.PeerInfo` entry, and creates the
        :class:`~piece_manager.PieceManager` and
        :class:`~logger.PeerLogger`. Opens no sockets -- that is
        :meth:`run`.

        Shared state established here:

        ``connections``
            ``dict[int, Connection]`` keyed by remote peer ID. A peer appears
            once, whether we dialled it or it dialled us.
        ``requested``
            ``set[int]`` of piece indices with an outstanding request to any
            neighbour. A piece in this set is not requested again; it is
            discarded when the piece arrives or when the neighbour chokes us.
        ``preferred``
            ``set[int]`` of currently preferred neighbour IDs.
        ``optimistic``
            ``Optional[int]``, the current optimistic neighbour.

        Raises
        ------
        config.ConfigError
            A config file is missing or malformed, or *peer_id* is not listed
            in ``PeerInfo.cfg``.
        """
        self.peer_id: int
        self.working_dir: str
        self.common: CommonConfig
        self.peers: list[PeerInfo]
        self.me: PeerInfo
        self.pieces: PieceManager
        self.log: PeerLogger
        self.connections: dict[int, Connection]
        self.requested: set[int]
        self.preferred: set[int]
        self.optimistic: Optional[int]
        self.rng: random.Random
        self._task_group: Optional[asyncio.TaskGroup]
        self._server: Optional[asyncio.Server]
        raise NotImplementedError

    # --- lifecycle ---------------------------------------------------------

    async def run(self) -> None:
        """Start listening, dial earlier peers, run until termination.

        Order matters: bind the listener *before* dialling, so a later peer
        that starts while we are still dialling can reach us. Then, inside one
        ``asyncio.TaskGroup``:

        1. serve the listening socket;
        2. dial every peer from :func:`config.peers_before` (with retries --
           peers are started by hand and an earlier one may still be coming
           up);
        3. start the preferred and optimistic timers from scheduler.py;
        4. one reader task per connection, added as connections appear.

        Returns when :meth:`check_termination` holds and :meth:`shutdown` has
        cancelled the group.
        """
        raise NotImplementedError

    async def _serve(self) -> None:
        """Run the listening socket, registering each inbound neighbour."""
        raise NotImplementedError

    async def _dial_earlier_peers(self) -> None:
        """Dial every peer listed before us, in file order.

        Logs ``makes a connection to`` per success, registers the
        connection, and sends our bitfield.
        """
        raise NotImplementedError

    async def register(self, conn: Connection, inbound: bool) -> None:
        """Add *conn* to ``connections``, log it, send our bitfield, read it.

        *inbound* picks the log line: ``is connected from`` for a peer that
        dialled us, ``makes a connection to`` for one we dialled. A second
        connection claiming an ID we already hold is closed and dropped.
        Starts the reader task for *conn* in the task group.
        """
        raise NotImplementedError

    async def _reader_task(self, conn: Connection) -> None:
        """Read messages from *conn* forever and dispatch each one.

        Exits on EOF, a closed socket, or cancellation. A
        :class:`messages.ProtocolError` from one neighbour closes that
        connection only; it must not take down the peer.
        """
        raise NotImplementedError

    async def dispatch(self, conn: Connection, msg_type: int, payload: bytes) -> None:
        """Decode *payload* and route it to the matching ``handle_*`` method.

        Raises
        ------
        messages.ProtocolError
            Unknown type, or a payload the type cannot carry.
        """
        raise NotImplementedError

    # --- message handlers --------------------------------------------------

    async def handle_bitfield(self, conn: Connection, bitfield_bytes: bytes) -> None:
        """Record their bitfield and reply ``interested``/``not interested``.

        Legal only as the first message after the handshake; a bitfield
        arriving later is a protocol error. A neighbour with no pieces sends
        none at all, which is why ``their_bitfield`` starts all-zero.
        """
        raise NotImplementedError

    async def handle_have(self, conn: Connection, index: int) -> None:
        """Set *index* in their bitfield, log it, re-evaluate interest.

        Logs ``received the 'have' message``. If *index* is a piece we lack
        and we were not interested, send ``interested``. A ``have`` that
        completes their bitfield may make us terminable -- check.
        """
        raise NotImplementedError

    async def handle_interested(self, conn: Connection) -> None:
        """Set ``peer_interested`` and log ``received the 'interested'``."""
        raise NotImplementedError

    async def handle_not_interested(self, conn: Connection) -> None:
        """Clear ``peer_interested`` and log the ``not interested`` line.

        The neighbour stays eligible for nothing until it is interested
        again; the next timer tick will choke it if it was unchoked.
        """
        raise NotImplementedError

    async def handle_choke(self, conn: Connection) -> None:
        """Mark us choked and release any outstanding request.

        Logs ``is choked by``. A ``pending_request`` that will now never
        arrive is removed from ``requested``, so the piece returns to the
        requestable pool for other neighbours.
        """
        raise NotImplementedError

    async def handle_unchoke(self, conn: Connection) -> None:
        """Mark us unchoked, log it, and send one request.

        Logs ``is unchoked by``, then :meth:`request_next`. If there is
        nothing interesting to ask this neighbour for, send nothing and wait
        for a ``have``.
        """
        raise NotImplementedError

    async def handle_request(self, conn: Connection, index: int) -> None:
        """Serve piece *index* unless we are choking them.

        A request from a choked neighbour is ignored (it raced with our
        ``choke``), as is a request for a piece we do not have. There is no
        ``cancel`` message and no pipelining: one piece, one reply.
        """
        raise NotImplementedError

    async def handle_piece(self, conn: Connection, index: int, data: bytes) -> None:
        """Store the piece, broadcast ``have``, re-evaluate, request again.

        In order:

        1. credit ``len(data)`` to their interval byte counter (the
           download-rate ranking key);
        2. write the piece and discard *index* from ``requested`` and from
           ``pending_request``;
        3. log ``has downloaded the piece`` with the new count;
        4. if now complete, log ``has downloaded the complete file``;
        5. send ``have`` to **all** neighbours, not just this one;
        6. re-evaluate interest with **every** neighbour, since this piece may
           have been the last one that made some of them interesting;
        7. send the next request to this neighbour if still unchoked;
        8. :meth:`check_termination`.

        A duplicate or unrequested piece is dropped after step 1.
        """
        raise NotImplementedError

    # --- protocol helpers --------------------------------------------------

    async def update_interest(self, conn: Connection) -> None:
        """Send ``interested``/``not interested`` to *conn* on a change.

        Interest is "they have at least one piece we lack" -- computed from
        the full bitfield, ignoring ``requested``, so a neighbour we have
        nothing to ask for *right now* still counts as interesting. Sends
        only when the flag flips, to avoid a storm of redundant messages.
        """
        raise NotImplementedError

    def pick_piece_to_request(self, conn: Connection) -> Optional[int]:
        """Pick a random piece to ask *conn* for, or ``None``.

        Candidates: pieces *conn* has, we lack, and that are not in
        ``requested``. Chosen uniformly at random with ``self.rng`` -- no
        rarest-first.
        """
        raise NotImplementedError

    async def request_next(self, conn: Connection) -> None:
        """Send one ``request`` to *conn* if it is appropriate.

        No-op when they are choking us, when ``pending_request`` is already
        set (one outstanding request per neighbour), or when
        :meth:`pick_piece_to_request` finds nothing. On success, records the
        index in both ``requested`` and ``conn.pending_request``.
        """
        raise NotImplementedError

    async def broadcast_have(self, index: int) -> None:
        """Send ``have`` for *index* to every connected neighbour."""
        raise NotImplementedError

    # --- scheduler callbacks -----------------------------------------------

    def neighbor_snapshots(self) -> list[NeighborSnapshot]:
        """Snapshot every connection for the selection functions."""
        raise NotImplementedError

    def reset_interval_counters(self) -> None:
        """Zero every neighbour's ``bytes_received_this_interval``."""
        raise NotImplementedError

    async def apply_preferred(
        self,
        preferred_ids: list[int],
        to_unchoke_ids: list[int],
        to_choke_ids: list[int],
    ) -> None:
        """Apply a :func:`scheduler.select_preferred` decision.

        Logs ``has the preferred neighbors``, sends ``unchoke`` to each newly
        unchoked neighbour and ``choke`` to each newly choked one, and updates
        ``preferred`` and the ``am_choking`` flags.
        """
        raise NotImplementedError

    async def apply_optimistic(self, peer_id: Optional[int]) -> None:
        """Apply a :func:`scheduler.select_optimistic` decision.

        ``None`` leaves the current neighbour in place and logs nothing.
        Otherwise log ``has the optimistically unchoked neighbor``, send
        ``unchoke`` if we are choking them, and store the new ID. The
        previous optimistic neighbour is *not* choked here -- it is choked by
        the next preferred-neighbour tick if it is not preferred.
        """
        raise NotImplementedError

    # --- termination -------------------------------------------------------

    def check_termination(self) -> bool:
        """Whether this peer and every neighbour hold the complete file.

        Requires a connection to every other peer in ``PeerInfo.cfg``, each
        with a complete ``their_bitfield``, plus our own
        :meth:`~piece_manager.PieceManager.is_complete`. Knowledge of a
        neighbour's completeness comes only from its bitfield plus the
        ``have`` messages it sent us.
        """
        raise NotImplementedError

    async def shutdown(self) -> None:
        """Close everything down cleanly.

        Waits :data:`SHUTDOWN_GRACE` seconds so last-moment ``have``
        messages land, then stops the listener, closes every connection,
        closes the piece manager and the log, and cancels the task group.
        Idempotent.
        """
        raise NotImplementedError


def main(argv: list[str]) -> int:
    """Parse ``argv``, build a :class:`PeerProcess`, and run it.

    ``argv[1]`` is the peer ID; anything else is a usage error on stderr with
    a non-zero exit status. The working directory is the process's current
    directory, per the spec.

    Returns
    -------
    int
        Process exit status: ``0`` on normal termination.
    """
    raise NotImplementedError


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv))
