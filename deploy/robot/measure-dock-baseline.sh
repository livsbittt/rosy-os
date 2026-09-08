#!/usr/bin/env bash
# measure-dock-baseline.sh — 도크 감지기 후보 벤치 계측 (ROSY-DOCK-001, D-28)
#
# 사용: ./measure-dock-baseline.sh <출력 CSV> <ambient>
#   ambient: dark | indoor | direct-sun
#
# 이 스크립트가 존재하는 이유: 후보 세 개를 같은 표에 담아야 비교가 되는데,
# 손으로 dock_probe 를 돌리면 캡처마다 라벨이 흔들린다. 아래 함정은 손으로
# 재면 거의 반드시 밟는다.
#
# 함정 1 — intensity 후보는 선행 확인 없이는 측정 자체가 무의미하다.
#   sllidar_ros2 가 C1 에서 `intensities` 를 상수로 채우면 역반사와 무광이
#   갈라질 수가 없다. 저장소의 rviz 스냅샷은 min=max=47 이었다. 그래서 이
#   스크립트는 먼저 그 필드를 찍어 보여주고, 상수로 보이면 경고한다.
#
# 함정 2 — 주변광 라벨을 안 남기면 IR 표본이 쓸모없어진다.
#   IR 은 주변광에 민감하고 판정을 가르는 것은 가장 밝은 구간이다. ambient 를
#   필수 인자로 받는 이유다.
#
# 함정 3 — 도크 없는 표본을 안 찍으면 거짓 양성 기준이 검사되지 않는다.
#   설계가 못 박은 벤치 하한은 50 장이고 `probe.MIN_ABSENT["bench"]` 가 그
#   숫자다. 모자라면 판정은 통과가 아니라 FAIL 로 나오므로 이 스크립트가
#   먼저 50 장을 찍는다. (전에는 10 장이었다 — 하한의 1/5 로 "거짓 양성 0"
#   을 인증할 참이었다.)

set -euo pipefail

OUT="${1:?출력 CSV 경로가 필요하다}"
AMBIENT="${2:?ambient 구간이 필요하다: dark | indoor | direct-sun}"

case "$AMBIENT" in
  dark|indoor|direct-sun) ;;
  *) echo "알 수 없는 ambient: $AMBIENT" >&2; exit 2 ;;
esac

echo "== 함정 1 확인: /scan 의 intensities =="
timeout 10 ros2 topic echo /scan --field intensities --once \
  | head -c 400 || echo "(intensities 를 읽지 못했다)"
echo
echo "위 값이 모두 같으면 intensity 후보는 측정 없이 탈락이다."
echo

echo "== 도크 없는 표본 (거짓 양성 + 주변광 바닥) =="
for _ in $(seq 1 50); do
  ros2 run rosy_bringup dock_probe --out "$OUT" --candidate geometry \
    --ambient "$AMBIENT" --no-dock
  ros2 run rosy_bringup dock_probe --out "$OUT" --candidate ir \
    --ambient "$AMBIENT" --no-dock
done

cat <<'GUIDE'

== 이제 수동 구간이다 ==
자로 잰 위치마다 아래를 실행한다. 거리는 접점에서 멀어지는 순서로.

  ros2 run rosy_bringup dock_probe --out OUT --candidate geometry \
    --ambient AMBIENT --distance 0.70 --lateral 0.00 --yaw-deg 0

  ros2 run rosy_bringup dock_probe --out OUT --candidate ir \
    --ambient AMBIENT --distance 0.03 --lateral -0.02

  ros2 run rosy_bringup dock_probe --out OUT --candidate intensity \
    --ambient AMBIENT --distance 0.50 --int-target 210 --int-baseline 45

보험으로 같은 창에서 함께 돌릴 것:
  ros2 bag record /scan /ir_sensor/range -o dock-bench-bag

판정:
  python3 -c "from pathlib import Path; from rosy_core.docking.probe import \
read_rows, verdict; [print(v) for v in verdict(read_rows(Path('OUT')))]"
GUIDE
