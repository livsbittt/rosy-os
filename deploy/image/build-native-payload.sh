#!/usr/bin/env bash
# Build the complete ROSY workspace into an offline native ROS 2 Jazzy payload.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE=""
RELEASE_ROOT=""
SOURCE_REVISION=""
ROS_DISTRO="jazzy"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace) WORKSPACE="${2:-}"; shift 2 ;;
        --release-root) RELEASE_ROOT="${2:-}"; shift 2 ;;
        --source-revision) SOURCE_REVISION="${2:-}"; shift 2 ;;
        --ros-distro) ROS_DISTRO="${2:-}"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail() { echo "FAIL: $*" >&2; exit 1; }

[[ "$(uname -m)" == "aarch64" ]] \
    || fail "native ROSY payloads must be built on aarch64"
[[ "$ROS_DISTRO" == "jazzy" ]] || fail "product ROS distribution must be jazzy"
[[ -d "$WORKSPACE/src" ]] || fail "workspace has no src directory: $WORKSPACE"
[[ -n "$RELEASE_ROOT" ]] || fail "--release-root is required"
[[ "$SOURCE_REVISION" =~ ^[0-9a-f]{40}$ ]] \
    || fail "--source-revision must be a full lowercase Git commit"
[[ -f "/opt/ros/jazzy/setup.bash" ]] || fail "native ROS 2 Jazzy is not installed"

ACTUAL_REVISION="$(git -C "$WORKSPACE" rev-parse HEAD)"
[[ "$ACTUAL_REVISION" == "$SOURCE_REVISION" ]] \
    || fail "workspace revision $ACTUAL_REVISION does not match $SOURCE_REVISION"
git -C "$WORKSPACE" diff --quiet || fail "workspace has unstaged changes"
git -C "$WORKSPACE" diff --cached --quiet || fail "workspace has staged changes"

mkdir -p "$RELEASE_ROOT"
RELEASE_ROOT="$(cd "$RELEASE_ROOT" && pwd -P)"
INSTALL_ROOT="$RELEASE_ROOT/install"
INVENTORY="$RELEASE_ROOT/rosy-packages.txt"
DEB_INVENTORY="$RELEASE_ROOT/deb-packages.txt"
NATIVE_RUNTIME_SOURCE="$WORKSPACE/deploy/robot/native"
[[ -d "$NATIVE_RUNTIME_SOURCE" ]] \
    || fail "native runtime support is missing: deploy/robot/native"
[[ ! -e "$RELEASE_ROOT/deploy/robot/native" ]] \
    || fail "release root already contains native runtime support"

# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash

rosdep install --from-paths "$WORKSPACE/src" --ignore-src -r -y \
    --rosdistro "$ROS_DISTRO"

(
    cd "$WORKSPACE"
    colcon build --base-paths src --merge-install \
        --install-base "$INSTALL_ROOT" --event-handlers console_direct+
    colcon list --base-paths src --names-only | LC_ALL=C sort -u > "$INVENTORY.tmp"
)
mv -f -- "$INVENTORY.tmp" "$INVENTORY"
dpkg-query -W -f='${Package}\t${Version}\n' | LC_ALL=C sort > "$DEB_INVENTORY.tmp"
mv -f -- "$DEB_INVENTORY.tmp" "$DEB_INVENTORY"
printf '%s\n' "$SOURCE_REVISION" > "$RELEASE_ROOT/source-revision.txt"
cp "$SCRIPT_DIR/required-ros-packages.txt" "$RELEASE_ROOT/required-ros-packages.txt"
mkdir -p "$RELEASE_ROOT/deploy/robot"
cp -a "$NATIVE_RUNTIME_SOURCE" "$RELEASE_ROOT/deploy/robot/native"

# shellcheck disable=SC1090
source "$INSTALL_ROOT/setup.bash"
"$SCRIPT_DIR/verify-package-inventory.sh" \
    --required "$SCRIPT_DIR/required-ros-packages.txt" \
    --inventory "$INVENTORY" \
    --install-root "$INSTALL_ROOT"

echo "PAYLOAD_BUILT $RELEASE_ROOT"
