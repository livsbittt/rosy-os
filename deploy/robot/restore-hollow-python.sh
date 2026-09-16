#!/bin/bash
# Restore 0-byte CPython files in Hub linux/arm64 ros:jazzy-ros-base (2026-09-16).
# Call after libpython3.12-* and python3-minimal have been reinstalled so python3 runs.
set -eo pipefail
mapfile -t py_pkgs < <(dpkg-query -W -f='${Package}\n' | grep '^python3-' || true)
if [ "${#py_pkgs[@]}" -eq 0 ]; then
  echo "restore-hollow-python: no python3-* packages" >&2
  exit 0
fi
apt-get install --reinstall -y --no-install-recommends "${py_pkgs[@]}"
