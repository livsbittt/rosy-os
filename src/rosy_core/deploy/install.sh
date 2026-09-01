#!/usr/bin/env bash
# install.sh — rosy-core.service 설치 (SRV-001, AT-01)
# 사용: sudo bash src/rosy_core/deploy/install.sh [워크스페이스_경로] [실행_사용자]
#   기본: 워크스페이스 = 스크립트 기준 상위 3단(리포 루트의 src/../install), 사용자 = rosy

set -euo pipefail

SERVICE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/rosy-core.service"
WS_PATH="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
RUN_USER="${2:-rosy}"

if [[ ! -f "$SERVICE_SRC" ]]; then
    echo "error: rosy-core.service not found at $SERVICE_SRC" >&2
    exit 1
fi
if [[ ! -f "$WS_PATH/install/setup.bash" ]]; then
    echo "error: workspace install not found at $WS_PATH/install — colcon build 먼저 실행" >&2
    exit 1
fi
if ! id "$RUN_USER" >/dev/null 2>&1; then
    echo "error: user '$RUN_USER' not found (두 번째 인자로 지정)" >&2
    exit 1
fi

UNIT_FILE="/etc/systemd/system/rosy-core.service"
sed "s|/home/rosy/rosy_ws|$WS_PATH|g; s|^User=.*|User=$RUN_USER|" "$SERVICE_SRC" > "$UNIT_FILE"

systemctl daemon-reload
systemctl enable rosy-core.service
echo "설치 완료: $UNIT_FILE"
echo "기동:     sudo systemctl start rosy-core"
echo "확인:     systemctl status rosy-core && journalctl -u rosy-core -f"
