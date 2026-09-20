# Pi 벤치 커미셔닝 설계 — 서명 artifact부터 hardware 모드까지

- 작성: 2026-09-20. 상태: Draft (벤치 Pi 대기). 관련: D-33, D-46, D-66,
  `docs/deployment/arm64-build-notes.md`,
  `docs/plans/2026-09-17-arm64-artifact-native-pi-plan.md`
- 목적: bench Pi 1대에서 서명된 artifact → 설치 → readback → 단계 승격의
  **순서와 각 문의 통과 조건**을 고정한다. 순서를 건너뛰지 않는다.

## 1. 전제

- 벤치: Raspberry Pi 5 + Pi OS Lite 64-bit, 유선 LAN, SD 굽기済み
- 빌드: native arm64 (QEMU 불가 — Hub hollow 이미지 실패 기록 유지).
  `ac81f2f` 개발 후보는 참조용이며 릴리스로 쓰지 않는다 (D-66 이후 CORE는
  `rosy_control`/OpenCV 미포함 — digest 재사용 금지)

## 2. 문 순서

| 문 | 명령 | 통과 조건 |
|---|---|---|
| G0 서명 | manifest + 서명 + immutable digest 발행 | digest 불변, 서명 검증 통과 |
| G1 설치 | `install-pi.sh` (`ROSY_ROBOT_NUMBER=1`) | `.env` identity 유도, 수동 identity 없음 (D-33) |
| G2 읽기 | `device-readback.sh --json` | manifest digest = running digest, `device_runtime=GO` |
| G3 정지 | `runtime-mode.sh up` (core) | stationary, `/dashboard` 도달, 단일 `cmd_vel` 발행자 |
| G4 모터 | motor 프로필 | `verify-motors.sh` 통과, deadman 확인 |
| G5 하드웨어 | hardware 프로필 | LiDAR + Nav2 goal 1회, `verify-pi.sh` 통과 |

- 각 문은 JSON 증거 보관. 실패하면 다음 문을 열지 않는다
- G3 이전에 motor/hardware를 켜지 않는다 (README 기동 순서)

## 3. 산출물

- 서명 manifest + 릴리스 digest (레지스트리)
- 문별 readback JSON (G2~G5)
- 실패 시 `release-recover` 동작 기록

## 4. 범위 밖

- 카메라 (별도 설계), 실물 도크 (별도 설계), FIELD 주행 (PARKED)
- Fleet 연결 (bench는 단독 — SAF-003 STOP 기본값 유지)
