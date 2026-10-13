"""Neighbour selection: preferred neighbours and the optimistic unchoke.

Responsibility
--------------
The choking policy, written as pure functions so it can be unit-tested with a
seeded ``random.Random`` and no sockets, no files and no event loop. The timer
loops at the bottom are deliberately thin: snapshot, decide, apply, reset
counters, sleep.

This module must NOT:
  * touch sockets, files or the log directly -- it calls back into
    peerProcess.py, which owns the connections and the logger;
  * import connection.py or peerProcess.py (the callbacks and
    :class:`NeighborSnapshot` keep this module leaf-level and testable).

Concurrency model: asyncio. Each timer is a ``while True: ... await
asyncio.sleep(interval)`` coroutine, started in the same ``asyncio.TaskGroup``
as the reader tasks.
"""

# Owner: Person C

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

#: What the scheduler needs to know about one neighbour. peerProcess.py builds
#: these from its Connection objects each interval; keeping it a plain value
#: object is what lets the selection functions be tested in isolation.
@dataclass(frozen=True)
class NeighborSnapshot:
    """An immutable view of one neighbour at the top of an interval.

    Attributes
    ----------
    peer_id:
        The neighbour's ID.
    peer_interested:
        They sent ``interested`` more recently than ``not interested``. Only
        interested neighbours are eligible for either selection.
    am_choking:
        We are currently choking them. Drives "newly unchoked" (so we send
        ``unchoke`` only on a transition) and the optimistic candidate rule
        ("choked and interested").
    bytes_received_this_interval:
        Payload bytes downloaded *from* them since the last reset. The
        download-rate ranking key -- intervals are equal length, so raw bytes
        order identically to a rate.
    """

    peer_id: int
    peer_interested: bool
    am_choking: bool
    bytes_received_this_interval: int


#: Returns the current neighbour snapshots, newest state each call.
NeighborProvider = Callable[[], list[NeighborSnapshot]]

#: Applies a preferred-neighbour decision: (preferred, to_unchoke, to_choke).
PreferredApplier = Callable[[list[int], list[int], list[int]], Awaitable[None]]

#: Applies an optimistic-unchoke decision; ``None`` means no eligible peer.
OptimisticApplier = Callable[[Optional[int]], Awaitable[None]]

#: Zeroes every neighbour's interval byte counter.
CounterReset = Callable[[], None]


def select_preferred(
    neighbors: list[NeighborSnapshot],
    k: int,
    have_complete: bool,
    rng: random.Random,
    optimistic_id: Optional[int] = None,
) -> tuple[list[int], list[int], list[int]]:
    """Choose the ``k`` preferred neighbours for the next interval.

    Candidates are the neighbours with ``peer_interested`` set. If
    *have_complete* -- this peer already has the whole file, so download rate
    carries no information -- choose ``k`` of them uniformly at random.
    Otherwise rank by ``bytes_received_this_interval`` descending and take
    ``k``, breaking ties **randomly** (shuffle with *rng* before the stable
    sort, so equal rates come out in a random order rather than in dict
    order). Fewer than ``k`` candidates means all of them are preferred.

    *optimistic_id*, when given, is the current optimistic neighbour: it is
    never included in ``to_choke``, because it stays unchoked even though it
    was not selected. It is not forced into ``preferred`` either -- a peer
    can be both, but only by being selected on its own merits.

    Returns
    -------
    ``(preferred_ids, to_unchoke_ids, to_choke_ids)``
        * ``preferred_ids`` -- the selected set, in the order chosen; this is
          what the ``has the preferred neighbors`` log line reports.
        * ``to_unchoke_ids`` -- selected neighbours we are currently choking
          (``am_choking``), i.e. the *newly* unchoked ones. Send ``unchoke``
          only to these; re-sending to an already-unchoked neighbour is
          wrong.
        * ``to_choke_ids`` -- neighbours we are currently *not* choking that
          were not selected and are not *optimistic_id*.

    Edge cases
    ----------
    ``k <= 0`` or no interested neighbours: all three lists are empty (the
    log line is still emitted by the caller). The function is pure: it reads
    *neighbors* and *rng* and mutates nothing.
    """
    raise NotImplementedError


def select_optimistic(
    neighbors: list[NeighborSnapshot],
    rng: random.Random,
) -> Optional[int]:
    """Choose one optimistically unchoked neighbour, uniformly at random.

    Candidates are neighbours that are **both choked by us**
    (``am_choking``) and ``peer_interested``. Returns ``None`` when there are
    none -- the caller then keeps, or drops, whatever it had and logs
    nothing, since the spec has no "no optimistic neighbour" line.

    Pure; uses only *rng* for randomness so a seeded test is deterministic.
    """
    raise NotImplementedError


async def run_preferred_timer(
    interval: int,
    get_neighbors: NeighborProvider,
    apply: PreferredApplier,
    reset_counters: CounterReset,
    k: int,
    have_complete: Callable[[], bool],
    rng: random.Random,
) -> None:
    """Every *interval* seconds, recompute and apply preferred neighbours.

    Loop body: snapshot, :func:`select_preferred`, ``await apply(...)``,
    ``reset_counters()``, sleep. Counters are reset *after* the decision so
    each interval ranks only that interval's traffic.

    Runs until cancelled (at termination). Never returns normally.
    """
    raise NotImplementedError


async def run_optimistic_timer(
    interval: int,
    get_neighbors: NeighborProvider,
    apply: OptimisticApplier,
    rng: random.Random,
) -> None:
    """Every *interval* seconds, recompute and apply the optimistic unchoke.

    Loop body: snapshot, :func:`select_optimistic`, ``await apply(...)``,
    sleep. Runs until cancelled; never returns normally.
    """
    raise NotImplementedError
