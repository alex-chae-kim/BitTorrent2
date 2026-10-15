#!/usr/bin/env bash
# Verify every peer ended up with a byte-identical copy of the shared file.
#
# Owner: Unclaimed
#
# Usage (from the working directory, after a run finishes):
#   scripts/verify.sh
#
# Run this and read the log files; a run that terminates is not necessarily a
# run that transferred the file correctly.
#
# TODO: implement
#   1. Read FileName and FileSize from Common.cfg, and the peer IDs from
#      PeerInfo.cfg.
#   2. Pick the reference copy: the first peer with hasFile 1.
#   3. For every peer directory, check the file exists, is exactly FileSize
#      bytes, and has the same checksum as the reference (shasum -a 256).
#   4. Print one PASS/FAIL line per peer; exit non-zero if any peer failed or
#      any peer directory is missing.

set -euo pipefail

echo "verify.sh: not implemented" >&2
exit 1
