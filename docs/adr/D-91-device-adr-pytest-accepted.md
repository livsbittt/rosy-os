## D-91 Device 비교 ADR은 호스트 pytest로 Accepted 하지 않는다

**Status:** Accepted (2026-09-17). D-79의 Device 쪽 적용이다.

**Context:** D-41·D-42·D-43·D-44·D-51·D-52는 본문이 ARM64 캡처, shadow 핸드오프,
보정 generation, OMX 실물, 다섯 safety 상태 실측을 요구한다. 호스트 pytest가
초록이면 이 여섯을 Accepted로 올리려는 시도가 반복된다.

**Decision:** 아래 ADR은 **각 본문의 Validation 측정이 Device/ARM64에 있을 때까지
Proposed**로 남는다.

| ADR | 열기 전에 필요한 증거 |
|---|---|
| D-41 | ARM64 캡처 위치 비교 (호스트 vs 최소권한 컨테이너) |
| D-42 | 50 Hz 예산에서 후보·안전 상관 실측 |
| D-43 | generation 격리 보정 쓰기·rollback |
| D-44 | Nav2 vs ControlBackend 실 시나리오, OMX 실물 interlock |
| D-51 | Pinky 프로필의 다섯 상태 행렬 + 바퀴 든 시험 |
| D-52 | ARM64 카메라 spike + shadow, 두 번째 실 publisher 없음 |

D-54·D-55·D-56은 소스/아키텍처 게이트만 Accepted이며 필드·payload·융합 승격은
HOLD다.

**Alternatives:** 여섯을 지금 Accepted 하는 안은 Validation을 지운다. 전부
Proposed로 남겨 D-54까지 묶는 안은 이미 닫힌 설정 게이트를 다시 연다.

**Consequences:** 다음 세션이 "나머지 ADR 처리"여도 D-41을 호스트에서 닫지 않는다.

**Validation / Transition:** 색인 Status가 Proposed인 여섯 ID. 호스트
`test_nav2_profile_limits.py` 통과는 D-54이지 D-51이 아니다.

**References:** D-79, D-80, D-87,
[device-validation](../plans/2026-09-13-rosy-os-device-validation-implementation-plan.md).
