# BitTorrent-style P2P File Sharing

A simplified BitTorrent clone in Python 3.11 (standard library only). Each
peer runs as its own process, connects to every other peer, exchanges
bitfields, and trades whole pieces of one shared file under a
choke/unchoke policy driven by download rate plus a periodic random
"optimistic" unchoke. A peer exits once it and all of its neighbours hold the
complete file.

Concurrency model: **asyncio**, one event loop per peer -- one reader task per
connection, two timer loops, all inside a single `asyncio.TaskGroup`
(Python 3.11+).

> Status: repository skeleton. Every function body is `raise
> NotImplementedError`; the log format strings in `logger.py` are the only
> real content. See the per-module docstrings for the contract each owner is
> implementing.

## Layout

```
Common.cfg          shared parameters (k, p, m, file name/size, piece size)
PeerInfo.cfg        peer ID, host, port, hasFile -- in start order
peerProcess.py      entry point + shared state + message handlers
config.py           config parsing
messages.py         wire format (handshake + framed messages)
piece_manager.py    bitfield + on-disk pieces in peer_<ID>/
logger.py           the graded log_peer_<ID>.log
connection.py       one TCP connection per neighbour
scheduler.py        preferred / optimistic neighbour selection
tests/              unittest, one file per module
scripts/            test-file generation, clean, verify
```

## Running locally

Everything is relative to the **working directory**: the directory holding
`Common.cfg` and `PeerInfo.cfg` (the repo root is fine). Each peer writes its
pieces to `peer_<peerID>/` and its log to `log_peer_<peerID>.log` there.

1. Generate the seed's copy of the file (peer 1001 has `hasFile 1`):

   ```bash
   python scripts/make_test_file.py
   ```

   For a quick run, shrink it: `python scripts/make_test_file.py --size 1048576`
   and set `FileSize` in `Common.cfg` to match.

2. Start one peer per terminal, **in `PeerInfo.cfg` order** -- each peer dials
   only the peers listed above it, so starting out of order means a peer tries
   to dial someone who is not listening yet:

   ```bash
   python peerProcess.py 1001   # terminal 1 (the seed)
   python peerProcess.py 1002   # terminal 2
   python peerProcess.py 1003   # terminal 3
   ...                          # through 1006
   ```

3. When the peers exit, check the result and the logs:

   ```bash
   scripts/verify.sh
   tail -n 5 log_peer_*.log
   ```

4. Reset between runs (keeps the seed's file):

   ```bash
   scripts/clean.sh
   ```

Running fewer than six peers is fine -- trim `PeerInfo.cfg` to the peers you
intend to start, since `check_termination` waits for every peer listed there.

## Tests

```bash
python -m unittest discover -s tests -v
```

All cases are currently `skip("not implemented")` placeholders that name and
document the behaviour to pin down. Un-skip them as you implement.

## Module ownership

Modules start unclaimed. To claim one, replace `Unclaimed` with your name in
this table and in the file's `Owner` marker. For shared work, list the names
in both places.

| Module | Owner | Responsibility | May import |
| --- | --- | --- | --- |
| `config.py` | Unclaimed | Parse `Common.cfg` / `PeerInfo.cfg`; `peers_before` | stdlib only |
| `piece_manager.py` | Unclaimed | Bitfield + pieces on disk in `peer_<ID>/` | `config` |
| `logger.py` | Unclaimed | The graded log, exact wording | stdlib only |
| `messages.py` | Unclaimed | Handshake and message framing | stdlib only |
| `connection.py` | Unclaimed | One TCP link per neighbour; transport only | `config`, `messages`, `piece_manager` |
| `scheduler.py` | Unclaimed | Preferred / optimistic selection, timer loops | stdlib only |
| `peerProcess.py` | Unclaimed (integration shared) | Startup, shared state, handlers, termination | all of the above |
| `scripts/` | Unclaimed | Test file, clean, verify | -- |
| Integration | shared | End-to-end runs, multi-host testing | -- |

**Dependency rule:** dependencies point downward only. `config`, `messages`,
`piece_manager` and `logger` must never import `connection`, `scheduler` or
`peerProcess`. That is what keeps the bottom four modules unit-testable
without a socket.

**Log rule:** the format strings in `logger.py` come from the spec and are
matched by the grader. Change them only to fix a mismatch with the spec, never
for taste, and never write anything else to the log file -- debug output goes
to stderr via `logger.debug`.

## TODO

- [ ] **Docker Compose multi-container run.** One service per peer off a
      single image, a shared volume (or a baked-in copy) for the generated
      file, and a `PeerInfo.cfg` whose hosts are the service names instead of
      `localhost`. Start order: `depends_on` is not enough on its own, because
      a peer must be *listening*, not merely started -- rely on
      `connect_to(..., retries=...)`.
- [ ] **Multi-host testing** (lab machines / VMs). Confirm `LISTEN_HOST`
      binding works off-loopback, replace the hosts in `PeerInfo.cfg` with
      real hostnames, and check that the ports are open. Add a small
      `scripts/run_remote.sh` to start peers over SSH in `PeerInfo.cfg` order.
- [ ] Decide whether to split the handlers out of `peerProcess.py` into
      `protocol.py` (see the note in its docstring) once they are real code.
- [ ] Add a timing/throughput summary to `verify.sh` for the report.
