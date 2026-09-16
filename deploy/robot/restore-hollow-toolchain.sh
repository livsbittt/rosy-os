#!/bin/bash
# Restore 0-byte / missing gcc, make, and cmake modules on Hub linux/arm64
# ros:jazzy-ros-base (2026-09-16). cmake itself is a real binary; Modules/*.cmake
# and /usr/bin/make are empty, and /usr/bin/gcc is absent.
set -eo pipefail
apt-get install --reinstall -y --no-install-recommends \
  build-essential \
  gcc \
  g++ \
  cpp \
  make \
  cmake \
  cmake-data \
  gcc-13 \
  g++-13 \
  cpp-13 \
  binutils \
  libc6-dev
command -v gcc
command -v g++
command -v make
test -s /usr/bin/make
test -s /usr/share/cmake-3.28/Modules/CMakeDetermineCCompiler.cmake
gcc --version | head -1
