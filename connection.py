"""One TCP connection to one neighbour.

Responsibility
--------------
Transport plus per-neighbour bookkeeping: perform the handshake, read framed
messages, serialise writes, and hold the flags that describe this link
(choked/interested in both directions, their bitfield, bytes received this
interval, the one outstanding request).

This module must NOT:
  * decide anything -- who to choke, what to request, when to terminate, what
    to log all live in peerProcess.py / scheduler.py;
  * write to the graded log;
  * import scheduler.py or peerProcess.py.

Concurrency model: asyncio. One reader task per connection awaits
:meth:`Connection.read_message` in a loop; every write goes through
:meth:`Connection.send`, which holds a lock so two tasks can never interleave
bytes of two messages on the same socket.
"""

# Owner: Person B

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from config import PeerInfo
from piece_manager import Bitfield

#: Seconds to wait for the handshake before giving up on a new connection.
HANDSHAKE_TIMEOUT = 30.0

#: Seconds between dial attempts when an earlier peer is not listening yet.
CONNECT_RETRY_DELAY = 1.0

#: Called with a fully handshaken inbound connection.
ConnectionHandler = Callable[["Connection"], Awaitable[None]]


class Connection:
    """A handshaken (or about-to-be-handshaken) link to one neighbour."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        num_pieces: int,
        remote_id: Optional[int] = None,
    ) -> None:
        """Wrap an open stream pair.

        *remote_id* is known up front for outbound connections and ``None``
        for inbound ones until :meth:`perform_handshake` fills it in.
        *num_pieces* is needed to decode their bitfield.

        Sets up the per-neighbour state:

        ``remote_id``
            Their peer ID, or ``None`` before the handshake.
        ``their_bitfield``
            :class:`~piece_manager.Bitfield`; starts all-zero, since a peer
            with no pieces may skip the bitfield message.
        ``am_choking``
            ``True`` -- everyone starts choked.
        ``peer_choking``
            ``True``.
        ``am_interested``
            ``False``.
        ``peer_interested``
            ``False``.
        ``bytes_received_this_interval``
            ``0``; payload bytes credited to this neighbour, reset by the
            unchoking timer and used as the download-rate ranking key.
        ``pending_request``
            ``None`` or the single piece index requested and not yet
            received.
        """
        self.reader: asyncio.StreamReader
        self.writer: asyncio.StreamWriter
        self.remote_id: Optional[int]
        self.their_bitfield: Bitfield
        self.am_choking: bool
        self.peer_choking: bool
        self.am_interested: bool
        self.peer_interested: bool
        self.bytes_received_this_interval: int
        self.pending_request: Optional[int]
        self._send_lock: asyncio.Lock
        raise NotImplementedError

    async def perform_handshake(
        self, my_id: int, expected_id: Optional[int] = None
    ) -> int:
        """Exchange handshakes and return the remote peer ID.

        Sends our handshake, reads exactly
        :data:`messages.HANDSHAKE_LEN` bytes, verifies the header, and stores
        the result in ``remote_id``.

        *expected_id* is the ID we dialled, for an outbound connection; a
        mismatch is a :class:`messages.ProtocolError`. Pass ``None`` for an
        inbound connection, where any ID is accepted here and the caller
        checks it against ``PeerInfo.cfg``.

        Raises
        ------
        messages.ProtocolError
            Bad header, or an ID that is not *expected_id*.
        asyncio.IncompleteReadError
            The peer closed mid-handshake.
        """
        raise NotImplementedError

    async def send_bitfield(self, bitfield: Bitfield) -> None:
        """Send our bitfield, or send nothing if we hold no pieces.

        Called once, immediately after the handshake. Skipping the message
        when ``count() == 0`` is explicitly allowed by the spec, so the
        receiver must not wait for one.
        """
        raise NotImplementedError

    async def read_message(self) -> tuple[int, bytes]:
        """Read one framed message and return ``(msg_type, payload)``.

        Reads the 4-byte length, then exactly ``length`` bytes, and splits
        off the type byte. The payload is returned undecoded; the caller
        passes it to :func:`messages.parse_payload`.

        Raises
        ------
        asyncio.IncompleteReadError
            Clean EOF or a truncated frame -- the reader task treats this as
            "neighbour gone".
        messages.ProtocolError
            A zero length, or a length beyond the largest legal piece
            message.
        """
        raise NotImplementedError

    async def send(self, msg_bytes: bytes) -> None:
        """Write pre-framed *msg_bytes* and drain.

        The only write path: it holds ``_send_lock`` for the whole write, so
        the timer tasks and a reader task may all send on this connection
        concurrently. A write to an already-closed connection is swallowed
        (logged to stderr), because a neighbour that finished and exited is
        normal at shutdown.
        """
        raise NotImplementedError

    def credit_bytes(self, n: int) -> None:
        """Add *n* received payload bytes to this interval's counter."""
        raise NotImplementedError

    def reset_interval_counter(self) -> int:
        """Zero ``bytes_received_this_interval`` and return its old value."""
        raise NotImplementedError

    def is_closed(self) -> bool:
        """Whether the writer has been closed."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close the stream and wait for it. Safe to call twice."""
        raise NotImplementedError


async def connect_to(
    peer_info: PeerInfo,
    my_id: int,
    num_pieces: int,
    retries: int = 0,
) -> Connection:
    """Dial *peer_info*, handshake, and return the live connection.

    With ``retries > 0``, a refused connection is retried every
    :data:`CONNECT_RETRY_DELAY` seconds -- useful because peers are started
    by hand in ``PeerInfo.cfg`` order and an earlier peer may not be
    listening the instant we start.

    The caller logs "makes a connection to" after this returns; it also sends
    the bitfield and starts the reader task.

    Raises
    ------
    OSError
        The dial failed (and retries, if any, were exhausted).
    messages.ProtocolError
        The handshake was bad or carried the wrong peer ID.
    """
    raise NotImplementedError


async def accept_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    my_id: int,
    num_pieces: int,
    valid_ids: set[int],
) -> Connection:
    """Handshake an inbound stream pair and return the connection.

    *valid_ids* is every peer ID in ``PeerInfo.cfg`` other than ours; an ID
    outside it, or one we already have a connection to, is rejected and the
    stream is closed.

    The caller logs "is connected from" after this returns.

    Raises
    ------
    messages.ProtocolError
        Bad header, or an ID not in *valid_ids*.
    """
    raise NotImplementedError


async def start_listener(
    host: str,
    port: int,
    my_id: int,
    num_pieces: int,
    valid_ids: set[int],
    on_connection: ConnectionHandler,
) -> asyncio.Server:
    """Listen on ``host:port`` and hand each handshaken peer to a callback.

    Returns the running :class:`asyncio.Server` so the caller can close it at
    shutdown. Each accepted stream is handshaken via
    :func:`accept_connection`; *on_connection* then registers it and starts
    its reader task. A handshake failure is reported to stderr and the stream
    dropped -- it must not bring down the listener.
    """
    raise NotImplementedError
