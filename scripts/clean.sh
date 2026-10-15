#!/usr/bin/env bash
# Remove the output of a previous run: logs and non-seed peer directories.
#
# Owner: Unclaimed
#
# Usage (from the working directory):
#   scripts/clean.sh          # logs + non-seed peer_*/ directories
#   scripts/clean.sh --all    # also remove the seed directories
#
# Keeps the seeds by default so you do not have to regenerate the test file
# between runs. Reads PeerInfo.cfg to tell a seed (hasFile 1) from a leecher.
#
# TODO: implement
#   1. cd to the repo root / working directory; bail if Common.cfg is missing.
#   2. rm -f log_peer_*.log
#   3. For each peer_*/ directory, remove it unless its peer ID has
#      hasFile 1 in PeerInfo.cfg (or --all was passed).
#   4. rm -rf __pycache__ tests/__pycache__
#   5. Print what was removed.

set -euo pipefail

echo "clean.sh: not implemented" >&2
exit 1
