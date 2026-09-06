# ROSY ADR Log
## Architecture Decision Records

**Document ID:** ROSY-ADR-001
**Version:** v1.0

> ADR은 "왜 그렇게 결정했는가"를 보존하는 기록이다. 결정 변경 시 기존 ADR을 수정하지 않고 Status를 `Superseded`로 변경하고 신규 ADR로 대체한다.
>
> 형식: **Status / Context / Decision / Consequences**

| ID | 제목 | Status |
|---|---|---|
| D-1 | 단일 프로세스 (rclpy + uvicorn 스레드) | Accepted |
| D-2 | 자체 cmd_vel 멀렉서 (Nav2 출력 remap) | Accepted |
| D-3 | Flask 완전 대체 — FastAPI 전면 이관 | Accepted |
| D-4 | Namespace + frame_prefix 조합 | Accepted |
| D-5 | Fleet↔로봇: 로봇 outbound WS + Fleet REST 명령 | Accepted |
| D-6 | 로봇 간 DDS 차단 (도메인 격리) | Superseded by D-33 |
| D-7 | React+TS+Vite, 빌드 산출물 정적 서빙 | Accepted |
| D-8 | 프로세스 내 이벤트 버스 | Accepted |
| D-9 | Waypoint 로컬 저장소 (JSON) | Accepted |
| D-10 | Fleet 프로토콜 envelope을 Phase 1에 조기 고정 | Accepted |
| D-11 | Capability 정적 YAML → API 노출 | Accepted |
| D-12 | Mission은 Fleet 전용, 로봇은 원자 액션 제공 | Accepted |
| D-13 | map_id = 맵 파일명 + 콘텐츠 체크섬 | Accepted |
| D-14 | 하드웨어 프로파일 계층 (벤더 중립 구조) | Accepted |
| D-15 | 플랫폼명 Rosy 확정 | Accepted |
| D-16 | 전면 리네임 (upstream 자동 병합 포기) | Accepted |
| D-17 | 문서 3+2 구조 및 계약 중심 거버넌스 | Accepted |
| D-18 | 프로토콜 스키마 재사용 — rosy_core 단일 소스 유지 | Accepted |
| D-19 | 접속 토폴로지: 로봇 WiFi 릴레이(AP+STA) 지원 | Superseded by D-26 |
| D-20 | Swarm 하이브리드: 오케스트레이션 Fleet / 폐루프 추종 로봇 탑재 | Accepted (D-12 확장) |
| D-21 | 군집 제어: 계층형 마스터-슬레이브 확정 + 분산 진화 훅 | Accepted (D-20 보강) |
| D-22 | Raspberry Pi OS 런타임: Core/I/O 컨테이너 분리 + 드라이버 deadman | Accepted |
| D-23 | Rosy OS 화면: FastAPI 내장 대시보드 + 읽기 전용 호스트 텔레메트리 | Accepted |
| D-24 | 절전: 센서 듀티 사이클링 + 초음파 웨이크 트리거 | Accepted |
| D-25 | 절전 계층은 STANDBY에서 끝난다 — Pi 5 하이버네이트 미채택 | Accepted |
| D-26 | 접속 토폴로지 재정리: SITE_STA 기본 + 릴레이(AP+STA) 장비별 옵트인 | Accepted (D-19 대체) |
| D-27 | 저배터리 셧다운은 D-25가 미채택한 halt의 유일한 예외 | Accepted |
| D-28 | 도킹: 액션이 Nav2 구간을 소유하고, 로봇이 도크를 폴링하며, 충전은 두 소스로 확인한다 | Accepted |
| D-30 | 현장 설정은 로컬 오버레이에만 쓰고, 토큰은 해시로만 남긴다 | Accepted |
| D-31 | 군집 참조 스트림은 로봇의 소켓이다 — Fleet 은 선택적 중계자 | Accepted |
| D-32 | 광고한 능력을 못 지키면 200 이 아니라 코드로 실패한다 | Accepted |
| D-33 | 로봇 신원은 하나의 로봇 번호에서 나온다 | Accepted (D-6 대체) |
| D-34 | 발행 주기는 그것을 읽는 쪽에 맞춘다 | Accepted |

---

## D-1 단일 프로세스 (rclpy + uvicorn 스레드)

**Status:** Accepted (2026-08)

**Context:** rosy_core는 ROS 2 노드와 Web API 서버를 모두 구동해야 한다. 별도 프로세스 + ROS 통신 구조도 가능했다.

**Decision:** 단일 프로세스로 Main Thread는 rclpy(MultiThreadedExecutor), Worker Thread는 uvicorn+FastAPI로 구동한다. 스레드 간 데이터는 State Manager의 불변 스냅샷 + 짧은 락으로 보호한다.

**Consequences:** 배포·상태 공유가 단순하다. 기존 Flask 서버도 동일 구조로 검증됨. 대신 장애 격리는 약하므로 systemd 재시작(D-1 보완)과 지연 모니터링에 의존한다.

---

## D-2 자체 cmd_vel 멀렉서

**Status:** Accepted (2026-08)

**Context:** 다중 명령 소스(Web·Fleet·Nav2·향후 Docking)와 E-Stop·모드 중재가 요구된다. `twist_mux` 패키지 사용도 검토했다.

**Decision:** Nav2 velocity_smoother 출력을 `nav_cmd_vel`로 리매핑하고, Command Manager가 **유일한 `cmd_vel` 퍼블리셔**가 되는 자체 멀렉서를 구현한다. E-Stop 상태머신·API·감사 로그와 결합.

**Consequences:** CORE SRS §8.1 요건(우선순위·차단·클리핑)을 완전 구현한다. twist_mux 대비 자체 유지보수 부담이 생긴다.

---

## D-3 Flask 완전 대체

**Status:** Accepted (2026-08)

**Context:** 기존 `pinky_navigation/scripts/nav2_web_server.py`(Flask, 560줄)가 존재한다. 병행 운용·레거시 경로 호환도 선택지였다.

**Decision:** 기존 기능 7종을 포함해 전부를 rosy_core FastAPI(`/api/v1/*`)로 재구현한다. 병행 운용·레거시 경로 호환은 하지 않는다. 기능 동등성 체크리스트 충족 시점에 Flask 런치 제거, Web 완성 후 코드 삭제.

**Consequences:** 이중 유지보수 제거, 단일 스택. 누락 방지를 위해 동등성 체크리스트(Impl Plan P0-7)로 관리한다. path/costmap 스냅샷 등 기존 기능이 계약(API Ref §5)에 명시되었다.

---

## D-4 Namespace + frame_prefix 조합

**Status:** Accepted (2026-08)

**Context:** 멀티로봇에서 ROS 토픽·TF 충돌을 방지해야 한다. 기존 `gz_bringup_launch.xml`이 namespace + `/tf→tf` 리매핑 패턴을 이미 검증했다.

**Decision:** namespace + frame_prefix 조합을 표준으로 한다(예: `/rosy_01/cmd_vel`, TF `rosy_01/odom`).

**Consequences:** 검증된 패턴 재사용으로 리스크 최소. 절대경로 토픽(`/scan` 등)은 제거 대상(Impl Plan P0-2).

---

## D-5 로봇 outbound WS + Fleet REST 명령

**Status:** Accepted (2026-08)

**Context:** Fleet이 로봇에 접속하면 인바운드 방화벽·mDNS·보안 정책 문제가 발생한다.

**Decision:** 로봇이 Fleet WS에 outbound 접속해 상태·이벤트를 push하고, 명령은 Fleet→로봇 REST로 전달한다.

**Consequences:** 네트워크·보안 단순화. 로봇은 Fleet 주소·토큰 설정만 필요하다. 명령 추적은 correlation_id + ack 모델(API Ref §7.5)로 보완한다.

---

## D-6 로봇 간 DDS 차단

**Status:** Superseded by D-33 (2026-09-06)

**Context:** 동일 WiFi에서 다수 로봇의 DDS 디스커버리 트래픽은 불안정의 주 원인이 된다(SRS §33).

**Decision:** 로봇별 고유 `ROS_DOMAIN_ID` + CycloneDDS localhost-only 프로파일로 로봇 간 DDS를 차단한다. 로봇 간 데이터는 Fleet 경유만.

**Consequences:** WiFi 안정성 확보. 시뮬레이션은 예외 프로파일로 처리 필요(Impl Plan P0-5).

---

## D-7 React + TS + Vite 정적 서빙

**Status:** Accepted (2026-08)

**Context:** 로봇 로컬 Web UI가 필요하다. 로봇 보드(RPi급) 리소스가 제한적이다.

**Decision:** React 18 + TypeScript + Vite로 개발하고, 빌드 산출물(dist)을 rosy_core가 정적 서빙한다(단일 포트 8080).

**Consequences:** 로봇에 Node 런타임 불필요, 부하 최소화. CI에서 프론트엔드 빌드 파이프라인 필요.

---

## D-8 프로세스 내 이벤트 버스

**Status:** Accepted (2026-08)

**Context:** Safety·Navigation·Command·System 이벤트를 감사 로그·WS 브로드캐스트·Fleet Agent가 공통 소비해야 한다.

**Decision:** rosy_core 내부에 경량 pub-sub 이벤트 버스를 두고, 모든 매니저가 EVT-001 표준 이벤트를 발행한다. 소비자(WS/audit/Fleet Agent)가 버스에 연결한다. 단조 증가 `seq` 부여는 버스 책임.

**Consequences:** 이벤트 소비자 추가가 코어 수정 없이 가능(확장성). 프로세스 외 전달은 WS/Fleet 프로토콜이 담당.

---

## D-9 Waypoint 로컬 저장소 (JSON)

**Status:** Accepted (2026-08)

**Context:** Waypoint는 로봇 독립 동작(Local-First)에 필요하므로 Fleet 의존 없이 보존되어야 한다.

**Decision:** 로봇 로컬 파일(JSON, `~/.rosy/waypoints.json`)을 원천 저장소로 한다. Fleet은 동기화 API로 읽기/내려보기만 한다(WPT-005).

**Consequences:** Fleet 장애에도 주행 가능. 로봇 다중화 시 Fleet이 조정(마지막 쓰기 승자 방지는 Fleet 동기화 순서로 관리).

---

## D-10 Fleet 프로토콜 envelope 조기 고정

**Status:** Accepted (2026-08)

**Context:** Fleet 구축은 Phase 4이지만, 프로토콜(envelope·heartbeat·ack·이벤트)을 늦게 정하면 Phase 4에서 로봇 측 재작업이 발생한다.

**Decision:** 프로토콜 envelope v1과 이벤트 모델을 Phase 1에서 스키마로 고정(공유 패키지/스키마 정의)하고, 로봇은 Phase 1부터 이 스키마로 이벤트·상태를 발행한다.

**Consequences:** Phase 4 착수 시 계약만 구현하면 됨. 초기 스키마 설계 오류 위험은 추가 전용 버저닝(PRT-006)으로 완화.

---

## D-11 Capability 정적 YAML → API 노출

**Status:** Accepted (2026-08)

**Context:** 이기종 로봇·AI 사전 검증을 위해 기능 선언이 필요하다. 동적 협상은 초기에 과하다.

**Decision:** Capability는 로봇의 정적 설정(YAML)에서 생성되어 `GET /system/capabilities`로 노출된다. Robot Profile(HWA)이 원천 데이터다(HWA-003).

**Consequences:** 구현 단순·예측 가능. 동적 capability(런타임 장착 등)는 capability_version 상향으로 확장.

---

## D-12 Mission은 Fleet 전용

**Status:** Accepted (2026-08)

**Context:** 미션 상태머신을 로봇에 두면 Fleet 장애 시에도 미션이 돌지만, 로봇별 중복 구현·디버깅 복잡도가 커진다.

**Decision:** Mission DSL 실행기는 Fleet에만 둔다. 로봇은 원자 액션(goto/home/stop/estop)과 이벤트를 제공한다. Local-First는 "기본 조작" 수준에만 적용한다.

**Consequences:** 로봇 단순화, 미션 로직 단일 위치. Fleet 장애 시 진행 중 미션은 중단되나 로봇 안전은 SAF-003이 보장.

---

## D-13 map_id = 맵 파일명 + 체크섬

**Status:** Accepted (2026-08)

**Context:** Fleet 맵 뷰와 Goal 검증(MAP-002)에 맵 동일성 판단 기준이 필요하다.

**Decision:** `map_id`를 `"{파일명}:{내용 체크섬 8자리}"` 형식으로 정의한다.

**Consequences:** 무결성 검증 내장, 중복 맵 자동 구분. 체크섬 변경(재저장) 시 새 map_id가 되는 점은 운용상 주의(버전 관리 정책은 Fleet Maps 화면에서 관리).

---

## D-14 하드웨어 프로파일 계층

**Status:** Accepted (2026-08)

**Context:** ROSY를 Pinky 전용이 아닌 범용 로봇 플랫폼으로 발전시킨다.

**Decision:** 하드웨어 종속(구동계·센서·속도 한계)을 Robot Profile(HWA-001)과 Driver Adapter(HWA-002) 뒤로 격리한다. Pinky Pro가 첫 어댑터 구현이다.

**Consequences:** 신규 로봇 지원 시 코어 수정 불필요(어댑터+Profile 추가). 첫 구현은 Pinky Pro 단일 어댑터이므로 인터페이스 추상화 과설계를 주의한다(2번째 로봇 도입 시점에 인터페이스 확정 다듬기).

---

## D-15 플랫폼명 Rosy 확정

**Status:** Accepted (2026-08)

**Context:** pinky_pro 포크를 기반으로 한 자체 플랫폼 명명이 필요했다. 후보: Brain, Corvus, Rook, Skein, Rosy 등. 색 언어유희 계열을 희망.

**Decision:** **Rosy**(ROS + Pinky 계보 언어유희, "장밋빛 전망")로 확정. 패키지 `rosy_core`/`rosy_web`/`rosy_fleet`, robot_id `rosy_NN`, hostname `rosy-NN`, 서비스 `rosy-core.service`. 하드웨어 모델명 "Pinky Pro"는 유지.

**Consequences:** 브랜드 일관성. 검색 시 일반 단어 혼입 가능성은 `rosy_core` 등 복합어 사용으로 완화.

---

## D-16 전면 리네임 (upstream 자동 병합 포기)

**Status:** Accepted (2026-08)

**Context:** 포크한 하드웨어 패키지(pinky_bringup 등)의 리네임 여부. 유지 시 upstream 병합 용이, 리네임 시 브랜드 일관성.

**Decision:** **전면 리네임**한다(rosy_bringup, rosy_navigation 등 전 패키지). upstream 개선사항은 자동 병합 대신 **수동 백포트**로 수용한다. 리네임은 P0-1에서 일괄 수행(패키지명·import·launch·config 경로·CI·systemd).

**Consequences:** 브랜드 일관성 최대, 리네임 비용은 초기(P0)에 1회 발생. upstream major 갱신 추적 노력 증가 — 참조 zip(reference/src)을 기준 버전으로 고정.

---

## D-17 문서 3+2 구조 및 계약 중심 거버넌스

**Status:** Accepted (2026-08)

**Context:** 단일 SRS가 로봇·플릿·계약을 모두 담아 책임이 모호해지고, Phase 4+ 확장 시 유지가 어려워졌다.

**Decision:** 문서를 5개로 분리한다 — ① CORE SRS(로봇 책임) ② FLEET SRS(플릿 책임) ③ API & Protocol Reference(공유 계약, 양측 합의 시에만 변경) ④ ADR Log(의사결정) ⑤ Implementation Plan(실행·추적). 문서 간 참조는 섹션 번호가 아닌 **요구사항 ID** 기반.

**Consequences:** 책임 경계 명확, 양측 독립 개발 가능(계약 문서만 공유). 원본 PKY 문서 2종은 재배치 후 삭제(이력은 각 문서 변경 이력에 승계).

---

## D-18 프로토콜 스키마 재사용 — rosy_core 단일 소스 유지

**Status:** Accepted (2026-08-29)

**Context:** P1-19에서 `rosy_core/protocol/schemas.py`(envelope·이벤트·ack)를 고정했다. Phase 4의 rosy_fleet도 동일 스키마가 필요하다. 독립 공유 패키지(예: rosy_protocol) 분리도 선택지였다.

**Decision:** 별도 패키지 분리는 보류하고, rosy_fleet이 `rosy_core`(ament_python 의존)를 import하여 재사용한다. 스키마 변경 시나리오는 양측이 같은 리포 내에서 동시 컴파일되므로 계약 파열이 구조적으로 차단된다.

**Consequences:** 초기 복잡도 최소화, 중복 제거. 단 rosy_fleet Docker 이미지에 rosy_core가 포함되는 부피와, 로봇 패키지 의존이 fleet 서버에 끼치는 영향은 P4 패키징 시 재검토(3번째 소비자 등장 시 분리 재고).

---

## D-19 접속 토폴로지: 로봇 WiFi 릴레이(AP+STA) 지원

**Status:** Superseded by D-26 (2026-09-02)

**Context:** 현장 네트워크 구성이 "로봇이 상위 WiFi에 연결된 채 AP처럼 동작해 무선을 릴레이"하는 방식으로 확인됨. 사용자 기기는 로봇 AP를 통해 로봇에 직접 접속한다.

**Decision:** 해당 토폴로지를 표준 배포 시나리오로 수용한다(NET-001~004). NetworkManager AP+shared 프로비저닝, 진입점은 mDNS(`rosy-01.local:8080`) + 게이트웨이 IP 폴백, 업링크 단절 시 AP 서브넷 내 제어 유지, Fleet은 로봇 아웃바운드 접속(D-5)으로 NAT 무관 동작.

**Consequences:** 단일 라디오의 AP+STA 동시 운용 제약(동일 채널)과 릴레이 대역폭 공유로 텔레옵 지연 변동 가능 — SAF-002 워치독과 속도 상한(SAF-004)이 완충. 상위 공유기 교체/채널 변경 시 로봇 AP 채널도 따라가므로 접속 가이드에 유의사항 기재.

---

## D-20 Swarm 하이브리드: 오케스트레이션 Fleet / 폐루프 추종 로봇 탑재

**Status:** Accepted (2026-08-29) — D-12 확장(미션 오케스트레이션 Fleet 전용 원칙은 유지)

**Context:** 기존 Formation 설계는 Leader pose를 Fleet이 받아 Follower별 목표를 계산·전송(약 2 Hz)하는 완전-중앙 방식이었다. 왕복 지연으로 추종이 울퉁불퉁해지고, Fleet 단절 시 형상이 즉시 붕괴된다. 로봇 자체가 군집 모드를 지원하면 좋은지 검토 요청이 있었다.

**Decision:** 하이브리드로 간다. Fleet은 지정·릴레이·중단 판단만(Leader pose 스트림 ≥10 Hz 수신 → Follower WS 릴레이 ≥5 Hz, `swarm/follow` 명령 1회). **폐루프 추종 계산은 로봇 탑재**(SWM-001~006): rosy_core이 pose 스트림을 소비해 moving-goal Nav2(≤2 Hz 갱신)로 추종하고, 스트림/Fleet 단절 시 로컬 HOLD(SWM-004). v2 대안(로컬 pure-pursuit cmd_vel 소스)은 CMD-001 등록 인터페이스로 예약.

**Consequences:** 추종 품질 향상(로컬 10 Hz 스트림 소비), Fleet 단절에도 형상·안전 로컬 유지, Fleet 부하 최소화. 로봇 코드에 follow 상태머신·스트림 타임아웃이 추가됨(복잡도 증가). Fleet은 릴레이 지연(≥5 Hz 보장) 품질에 영향을 주므로 적합성 테스트(P4-6)에 포함.

---

## D-21 군집 제어: 계층형 마스터-슬레이브 확정 + 분산 진화 훅

**Status:** Accepted (2026-08-29) — D-20 보강

**Context:** 군집을 마스터-슬레이브로 할지 분산(P2P)으로 할지 검토했다. 분산의 이점: Fleet 단절에도 형상 유지. 분산의 비용: 리더 선출·합의·분산 안전 중재(검증 난이드 급증), 로봇 간 신규 통신 채널. 결정적 사실: WiFi 릴레이 토폴로지(NET-001)에서 로봇 간 통신도 상위 공유기 경유로 동일 무선 매체를 공유하므로 P2P의 지연 이점이 대부분 상쇄된다.

**Decision:**
1. **계층형 마스터-슬레이브로 확정** — Fleet = 형성 오케스트레이션 마스터(지정·슬롯 배정·중단 판단), Leader 로봇 = 형성 기준(참조 스트림 발행), Follower = 슬레이브(로컬 폐루프 추종, SWM-002).
2. **분산 진화 훅**: 로봇측 follow 소비자는 참조 pose 스트림의 **소스를 묻지 않는다**(`source: fleet|peer`, 기본 `fleet`). 향후 P2P 유니캐스트 소스가 추가돼도 로봇 추종 로직·계약은 불변.
3. **재검토 트리거** (하나라도 충족 시 분산 재고): ≥20대 동시 군집 / Fleet 링크 지연 >200 ms 지속 / Fleet-리스 완전 자율 군집 요구 / 로봇 간 직접 링크(상위 공유기 미경유) 확보.

**Consequences:** 초기 구현 단순·안전 책임 명확·기존 계약 유지. 분산 전환은 소스 어댑터 추가 + ADR 스퍼세드로 가능하도록 인터페이스만 예약(과설계 방지 — 구현은 트리거 발생 시).

---

## D-22 Raspberry Pi OS 런타임: Core/I/O 컨테이너 분리 + 드라이버 deadman

**Status:** Accepted (2026-08-31)

**Context:** 제품의 1차 장치는 Raspberry Pi 5 8GB와 Raspberry Pi OS Lite
64-bit다. ROS 2 Jazzy의 기존 네이티브 배포안은 Ubuntu 24.04를 전제로
하고 있으며, 현재 `rosy_core`는 장치를 직접 열지 않고 `rosy_bringup` 등
Driver Adapter를 통해 명령한다. 단일 컨테이너는 FastAPI와 모든 장치
권한을 결합하고, 한 노드의 장애가 전체 런타임 재시작으로 확대된다.

**Decision:** Ubuntu Noble 기반 ROS 2 Jazzy 사용자 공간을 OCI 이미지로
제공한다. 런타임은 장치 권한이 없는 `rosy-core`와 Pinky Pro 장치
어댑터를 실행하는 `rosy-io`로 나눈다. 두 서비스는 동일한 host network,
`ROS_DOMAIN_ID`, localhost CycloneDDS 정책으로 통신한다. `rosy-io`에는
열거된 장치만 전달하며 `privileged` 모드는 금지한다. 모터 어댑터는 마지막
정상 `cmd_vel` 이후 설정된 시간(기본 500 ms)이 지나면 독립적으로 zero RPM을
명령한다.

**Consequences:** Raspberry Pi OS 호스트에 ROS 2를 별도로 포팅하지 않고
Jazzy 사용자 공간을 고정할 수 있으며, 외부 API와 장치 권한이 분리된다.
반면 host networking, 장치 UID/GID, 이미지 빌드·승격, 두 서비스의 장애
복구를 운영해야 한다. 소프트웨어 deadman은 안전 인증 수단이 아니며,
고위험 용도에는 하드웨어 E-stop 또는 독립 컨트롤러가 추가로 필요하다.

---

## D-23 Rosy OS 화면: FastAPI 내장 대시보드 + 읽기 전용 호스트 텔레메트리

**Status:** Accepted (2026-09-01)

**Context:** Raspberry Pi OS에서 `rosy_core`를 운영하려면 로봇 상태뿐 아니라
CPU, 메모리, 저장소, 온도와 런타임 오류를 현장에서 확인할 화면이 필요하다.
별도 React/Node 서비스는 첫 Pi 5 런타임의 프로세스·배포·장애 표면을 늘린다.
반대로 core 컨테이너에 Docker socket, host root 또는 systemd 제어 권한을
주면 D-22의 Core/I/O 최소권한 분리를 훼손한다.

**Decision:** FastAPI가 `/dashboard`와 로컬 HTML/CSS/JavaScript 자산을 직접
제공한다. 로봇 상태와 제어는 기존 인증된 REST/WebSocket 계약을 재사용한다.
호스트 상태는 `/proc` 핵심 파일, `/sys/class/thermal`과 그 심볼릭 링크 대상인
`/sys/devices/virtual/thermal`, `/etc/os-release`,
`/etc/hostname`만 개별 read-only mount하여 수집한다. 임의 셸 실행, host root,
Docker socket, systemd 제어 및 OS 설정 변경은 대시보드 범위에서 제외한다.

**Consequences:** 별도 프론트엔드 런타임 없이 오프라인 현장 화면을 제공하고
기존 API 역할·감사 경계를 유지한다. host 파일이 없거나 플랫폼이 다르면 일부
값은 `unavailable`로 표시된다. 향후 네트워크·업데이트·재부팅을 제어하려면
별도 최소권한 host agent와 명시적인 명령 계약을 새 ADR로 설계해야 한다.
모드 변경은 UI 확인과 중복 요청 잠금을 거치며 서버가 capability를 재검사한다.
내비게이션 속도 표본은 500 ms 뒤 만료되어 stale 명령 재생을 막는다.

---

## D-24 절전: 센서를 끄지 않고 듀티 사이클링하며 초음파를 웨이크 트리거로 쓴다

**Status:** Accepted (2026-09-01)

**Context:** 세워둔 Rosy의 상시 소비원은 둘이다. `rosy_sensor_adc`는 I2C ADC
5채널을 20 Hz로 폴링하는데 채널당 6 ms 왕복이라 한 사이클이 약 30 ms이고,
`rosy_emotion`은 240x320 RGB565 프레임을 10 Hz로 SPI에 밀면서 백라이트를
100% PWM으로 유지한다. 그러나 어느 쪽도 그냥 끌 수 없다. 초음파 채널은 사람이
다가온 것을 알아채야 하는 웨이크 트리거이고, 배터리 채널은 SAF-005 정책에
계속 값을 공급해야 한다. 별도의 저전력 웨이크 IC나 터치 센서는 현재 하드웨어에
없다.

**Decision:** 종료가 아니라 듀티 사이클링을 택한다. `rosy_core`의
`PowerManager`가 ACTIVE/IDLE/STANDBY를 결정해 `power/mode`로 발행하고,
하드웨어 노드는 그 모드를 자기 장치 동작으로만 번역한다. ADC는 20/5/2 Hz로
주기를 바꾸고 STANDBY에서는 초음파·배터리 채널만 읽는다. LCD는 IDLE에서
디밍, STANDBY에서 백라이트 소등과 슬립 진입, SPI 전송 중단을 한다.
웨이크 센서는 초음파 하나이며, 양방향 디바운스와 히스테리시스로 판정하고
`contact_m` 이내는 접촉으로 간주한다. 절전은 표시·샘플링 정책일 뿐 모터
권한이 없다 — 명령·비 IDLE 모드·배터리 경보는 즉시 ACTIVE로 되돌린다.

**Consequences:** STANDBY에서 I2C 왕복이 사이클당 5회에서 2회로, 폴링이
20 Hz에서 2 Hz로 줄고 백라이트가 꺼진다. 2 Hz에서도 접근한 손은 500 ms 안에
검출되어 체감 지연이 없다. 대신 STANDBY 동안 IR 채널이 발행되지 않으므로 이
토픽에 의존하는 소비자는 ACTIVE를 전제해야 하고, 웨이크 판정이 초음파 시야에
묶여 사각지대가 남는다. ADC 노드는 유효한 `power/mode`를 받기 전까지 기동
주기를 유지하므로 `rosy_core` 장애가 센서를 느리게 만들지는 못한다.
IR·IMU 기반 보조 웨이크가 필요하면 별도 ADR로 다룬다.

---

## D-25 절전 계층은 STANDBY에서 끝난다 — Pi 5 하이버네이트는 채택하지 않는다

**Status:** Accepted (2026-09-01)

**Context:** D-24의 듀티 사이클링 아래로 한 단계 더 내려갈 수 있는지 조사했다.
Raspberry Pi 5는 2026년 중반 기준 suspend-to-RAM(`mem`)도 하이버네이트(`disk`)도
지원하지 않는다. BCM2712에 상시 도메인 하드웨어는 있으나 Broadcom SDRAM PHY
self-refresh 시퀀스가 공개되지 않아 펌웨어 경로가 막혀 있다. 실제로 존재하는
유일한 딥 상태는 `POWER_OFF_ON_HALT=1` + `halt`로 PMIC를 STANDBY에 넣는 약 3 mA
상태이며, Pi 5에서는 `WAKE_ON_GPIO`가 의미를 잃어 전원 버튼과 RTC 알람만이 웨이크
소스다. 즉 Pi 5의 전력 상태는 상시 약 2.7 W 아니면 사실상 꺼짐이고 중간 단계가
없다. 한편 세워둔 로봇의 소비는 DYNAMIXEL 홀딩 토크, 상시 회전하는 RPLIDAR C1
모터, LCD 백라이트, SoC 순이라 SoC는 목록의 맨 위가 아니다.

**Decision:** 절전 계층을 ACTIVE/IDLE/STANDBY에서 끝내고 딥 halt를 그 아래
단계로 채택하지 않는다. 네 가지가 D-24의 계약과 충돌하기 때문이다. (1) 웨이크
센서가 함께 죽는다 — halt된 Pi는 초음파를 샘플링하지 못하므로 D-24의 유일한
웨이크 트리거가 사라지고 RTC 예약과 물리 버튼만 남는다. (2) 복귀가 resume이
아니라 부팅이라 Docker/ROS 2 그래프 재기동까지 수십 초가 걸려 500 ms 목표와
자릿수가 다르다. (3) E-Stop, 50 Hz `cmd_vel`, teleop 워치독, SAF-005가 모두
멈춰 "절전은 모터 권한이 없다"는 경계를 깬다. (4) DDS 디스커버리·오도메트리·
SLAM 세션·진행 중 목표가 소실된다. 대신 실효 절감을 LiDAR 모터로 돌린다
(PWR-005): `sllidar_ros2`의 `stop_motor`/`start_motor`를 STANDBY에 연결하되
`power.lidar.standby_stop`은 기본 `false`로 출하해 벤치 승인 뒤 켠다. 모터 토크
오프는 절감이 가장 크지만 전력 정책이 액추에이터 상태를 지시하게 되어 경계를
넘으므로 별도 ADR로 유보한다.

**Consequences:** 세워둔 로봇에서 Pi의 2.7 W는 회수 대상이 아니며, 남은 절감은
주변장치에서만 나온다. LiDAR 정지는 코드 경로가 완성·단위 검증되었지만 기본
비활성이라 실측 이득은 벤치 승인 전까지 0이고, 스캔 단절이 실행 중 Nav2
라이프사이클에 주는 영향은 실기 관찰 항목으로 남는다. 정지 상태에서 재기동
후 스캔을 신뢰하기까지의 창은 `lidar_ready`로 노출되며 `spinup_s: 2.0`은
아직 추정값이다. 근접 웨이크를 유지한 채 호스트를 재우려면 초음파를 쥐고
전원 버튼/`GLOBAL_EN`을 구동하는 상시 MCU가 필요해 보드 변경 사안이 된다.
Jetson·x86처럼 서스펜드가 제대로 되는 컨트롤러로 확장할 때는 `PowerManager`를
정책 소유자로 두고 `PlatformPowerBackend`가 자기 능력을 선언하는 형태로 가며,
그 시점에 별도 ADR로 다룬다. 조사 근거와 출처는
`docs/plans/2026-09-01-deep-power-states-design.md`에 있다.

**Amendment (2026-09-02):** 이 결정은 `halt`를 *절전 계층의 한 단계*로
채택하지 않는다는 뜻이며, 모든 `halt`를 금지하는 것이 아니다. D-27이 배터리
안전 정책에서 오는 단 하나의 예외를 인터록과 함께 기록한다. 위 (1)~(4)의
반론은 그대로 유효하지만 전부 "깨어날 것을 전제한 절전"에 대한 것이고,
D-27의 셧다운은 깨어남을 전제하지 않는다 — 사람이 충전기를 꽂는 것이
복귀 절차다. 두 결정은 함께 읽어야 한다.

---

## D-26 접속 토폴로지 재정리: SITE_STA 기본 + 릴레이(AP+STA) 장비별 옵트인

**Status:** Accepted (2026-09-02) — D-19 대체

**Context:** D-19은 "로봇이 상위 WiFi에 STA로 붙은 채 동시에 자체 AP로 무선을
릴레이하고 사용자 기기는 로봇 AP로 접속한다"를 **표준** 배포 시나리오로 못박았다.
ROSY OS v1 이미지·릴리스 설계를 진행하면서 이 전제가 두 방향에서 압박을 받았다.

한편으로 릴레이는 실제 현장 요구다. 상위 공유기가 없거나 신뢰할 수 없는 장소,
작업자가 로봇에 직접 붙어야 하는 시운전 상황에서 릴레이는 대체재가 없다. 이
요구는 사라지지 않았다.

다른 한편으로 릴레이를 **모든 장비의 기본**으로 두면 비용이 붙는다. Pi 5의 단일
라디오에서 AP와 STA는 같은 채널을 공유하므로 상위 공유기가 채널을 바꾸면 로봇 AP도
따라 움직인다. 로봇을 여러 대 같은 사업장에 놓으면 각 로봇이 자기 AP를 열어 2.4/5 GHz
대역에 서로 간섭하고, 릴레이 NAT가 로봇마다 별도 서브넷을 만들어 Fleet과 작업자
단말의 주소 체계를 복잡하게 만든다. 게다가 상시 AP는 첫 부팅 프로비저닝용 임시 AP와
수명주기가 달라, 하나의 무선 인터페이스에 두 종류의 AP 정책이 겹친다.

즉 릴레이는 **필요하지만 기본값으로는 비싸다**. D-19의 오류는 릴레이를 지원한
것이 아니라 그것을 유일한 표준으로 규정한 것이다.

**Decision:** 접속 토폴로지를 두 모드로 나누고 기본값을 바꾼다.

- `SITE_STA` — **기본값.** 로봇이 사업장 WLAN에 STA로 참여한다. 작업자 단말, Site
  Fleet, 다른 로봇이 같은 WLAN에 있고 로봇은 AP를 열지 않는다. 다수 로봇 사이트의
  정상 운용 모드다.
- `RELAY_AP_STA` — **장비별 옵트인.** D-19이 규정한 AP+STA 릴레이를 그대로 유지한다.
  NetworkManager AP + shared 로 프로비저닝하고, 사용자 기기는 로봇 AP를 통해 로봇에
  직접 접근하며 상위 WiFi가 있으면 릴레이한다. 설정으로 명시적으로 켤 때만 동작한다.

두 모드는 **동일한 첫 부팅 설정 AP**로 프로비저닝된다. 설정 AP는 프로비저닝 전용
임시 모드이며 릴레이 AP와 별개다. 운용 모드 선택은 프로비저닝 단계에서 이루어지고
장비별 설정에 기록된다.

릴레이는 v1 범위 안이다. 후속 Capability로 미루지 않는다.

**Consequences:** D-19의 릴레이 구현 요구는 살아남고 NET-001~004도 폐기되지 않는다.
다만 NET-001은 "릴레이가 가능해야 한다"에서 "두 모드를 지원하되 기본은 SITE_STA"로
바뀌고, NET-002/003/004는 두 모드 각각에서 성립하도록 읽혀야 한다. 특히 NET-003의
"업링크 단절 시 로컬 유지"는 릴레이 모드에서는 로봇 AP 서브넷 안에서, STA 모드에서는
사업장 WLAN 안에서 성립하며 후자는 공유기의 client isolation 설정에 의존한다 — 이
둘은 서로 다른 실패 양상을 가지므로 인수 시험에서 별도 항목으로 기록한다.

네트워크 상태머신은 모드 하나가 아니라 둘을 표현해야 하고, 대시보드의 네트워크 카드도
현재 모드를 세 값(`PROVISIONING_AP` / `SITE_STA` / `RELAY_AP_STA`) 이상으로 구분해
보여야 한다. 릴레이의 채널·간섭 제약은 사라진 것이 아니라 옵트인한 장비에 국한된다.
그 제약은 접속 가이드에 남긴다.

설계 근거는 `docs/plans/2026-09-01-rosy-os-v1-image-release-design.md`에 있다.

---

## D-27 저배터리 셧다운은 D-25가 미채택한 halt의 유일한 예외

**Status:** Accepted (2026-09-02)

**Context:** SAF-005는 크리티컬에서 `RETURN_HOME` 또는 `STOP`까지만 정의한다.
그 아래로 계속 방전되면 결국 팩 보호 회로가 컷오프하는데, 이는 셀을 지키는
동작이지 호스트를 지키는 동작이 아니다. Raspberry Pi 입장에서는 루트
파일시스템이 마운트되고 Docker가 쓰고 있는 상태에서의 예고 없는 전원 제거이며,
반복되면 SD 카드 손상으로 이어진다. 즉 여기서 보호 대상은 셀이 아니라
파일시스템이다. 한편 D-25는 Pi 5의 `halt`를 "채택하지 않는다"고 기록했고,
문서 자체가 그런 상태는 "같은 idle 타이머에서 도달 가능해서는 안 된다"고 썼다.
배터리 안전 경로는 idle 타이머가 아니지만, D-25의 문구를 해석으로 우회해서
기계를 끄는 코드를 넣을 수는 없다.

**Decision:** 배터리 정책에서 출발하는 셧다운 하나를 D-25의 예외로 채택하고,
다음 인터록을 함께 고정한다. (1) 배터리 정책에서만 도달 가능하다 — 어떤 dwell
타이머, 어떤 무활동 경로에서도 도달할 수 없다. (2) SAF-005 아래 신설된 `deep`
단계를 `battery_deep_dwell_s` 동안 유지해야 무장된다. 표본 수가 아니라 초 단위
조건이므로 어떤 필터 튜닝으로도 순간값이 셧다운을 일으킬 수 없다. (3) 회복하면
취소된다 — 무장이 풀리면 센티넬이 삭제되고, 유예 중 충전을 시작하면 별도 신호
없이 셧다운이 철회된다. (4) 모터를 먼저 세운 뒤에만 진입한다. 실행 경로는 Host
Agent가 아니라 일방향 센티넬이다: CORE가 `/var/lib/rosy`에 관찰을 기록하고
호스트의 `rosy-lowbatt-shutdown.path`/`.service`가 신선도를 스스로 판정해
실행한다. Host Agent의 모든 명령은 `administrator` + 확인 필수인데 배터리 정책은
확인해 줄 사람이 없어, 그 경로를 쓰면 무인·무확인 실행 예외를 뚫어야 하고 이는
D-22가 세운 경계 자체를 약화시킨다.

**Amendment (2026-09-02, D-28):** 인터록이 하나 늘었다. **확인된 충전은
셧다운을 억제한다.** 4%에 도크에 도착한 로봇은 수 분간 `deep` 을 유지하므로,
억제가 없으면 충전기 위에서 halt 하고 D-25 대로 다시 깨어나지 못한다.
충전에 성공하고 벽돌이 되는 것은 그냥 방전되는 것보다 나쁘다. "확인된"은
도크의 주장이 아니라 도크가 보고한 전류 **그리고** 떨어지지 않는 팩 전압을
뜻한다 — LAN 의 장치 하나가 말만으로 안전 경로를 끄지 못하게 하기 위해서다.

**Consequences:** 로봇이 스스로 꺼질 수 있게 되었고, 이는 되돌리려면 사람이
가야 하는 동작이다. 그래서 오발화 비용이 크고, 그 대가로 dwell·히스테리시스·
호스트측 재확인이라는 삼중 조건이 붙는다. `.service`에 `[Install]` 절이 없어
path 유닛만이 이를 기동할 수 있다 — `/var/lib/rosy`가 영속이므로 불결한 종료가
남긴 센티넬이 다음 부팅을 끄는 것을 이 구조가 막는다. 호스트는 센티넬의
`grace_seconds`를 상한으로 클램프하므로 컨테이너 쪽 값이 무한정 대기를 만들 수
없다. 반대 방향의 한계도 분명하다. 전류 센싱이 없어 잔량은 추정치이고, 주행
중에는 전압 새그로 실제보다 낮게 읽힌다 — `deep` 임계를 5%로 낮게 잡고 dwell을
건 이유가 이것이다. 그리고 이 셧다운은 "충전하러 갈 곳"을 전제하지 않는다.
도킹스테이션이 생기면 `deep` 진입 전에 도크 복귀를 시도하는 단계가 그 위에
들어가야 하며, 그때 이 결정을 다시 읽어야 한다. 설계 근거는
`docs/plans/2026-09-02-battery-integrity-low-battery-alert-design.md`에 있다.

---

## D-28 도킹: 액션이 Nav2 구간을 소유하고, 로봇이 도크를 폴링하며, 충전은 두 소스로 확인한다

**Status:** Accepted (2026-09-02)

**Context:** 도킹은 첫 SRS 이래 스텁이었다 — `docking.supported=false`, 두
엔드포인트에 501, 우선순위 슬롯 4 예약, `RobotMode.DOCKING` 은 enum 에만 존재.
실물 도크를 설계하면서 코드가 이미 정해둔 세 가지가 설계를 제약했다. (1)
`RETURN_HOME` 은 예약 waypoint `__home__` 을 찾는데 그것을 만드는 코드가
리포에 없어, 기본 크리티컬 정책이 실제로는 STOP 으로 동작해 왔다. (2) 모드
전이표가 `NAVIGATION → DOCKING` 을 막아 "스테이징 주행 후 도킹 전환"이 표현
불가능하다. (3) `Waypoint` 는 포즈만 담아 기종·스테이징 오프셋·에이전트 주소를
가진 도크를 표현할 수 없다. 여기에 하드웨어 제약이 겹친다: `batt_state` 의
`current`·`percentage` 는 NaN 이고 `power_supply_status` 는 `UNKNOWN`
하드코딩이라, 로봇에는 "충전 중"을 알 신호가 하나도 없다.

**Decision:** 넷을 함께 정한다. **(1) 도킹 액션이 Nav2 구간을 소유한다.**
전이표에 간선을 더하는 대신 명령 수락부터 도킹 완료·실패까지 `DOCKING` 모드를
쥔다. 표를 건드리지 않고, `DOCKING`(4) > `NAVIGATION`(5) 이므로 도크에 반쯤
들어간 로봇을 Fleet 주행 명령이 밀어내지 못하는 성질을 공짜로 얻는다. Nav2 의
`opennav_docking` 도 같은 구조다. **(2) 도크를 계측하고 로봇이 폴링한다.**
도크는 어느 로봇이 오는지 모르고 로봇은 자기가 갈 도크를 안다. 도크가 밀어넣는
구조는 로봇 API 에 인증 없는 인바운드를 열고, Fleet 경유는 Fleet 이 죽으면
충전을 막는다. 도크에 MCU 를 두는 근거는 전류 보고가 아니라 **바닥의 상시 통전
접점이 위험하다**는 것이다 — 부하를 감지한 뒤에만 통전한다. **(3) 충전은 독립된
두 소스로 확인한다** — 도크가 보고한 전류 그리고 떨어지지 않는 팩 전압. 이
판정이 D-27 셧다운 억제의 입력이라, 단일 소스면 LAN 의 장치 하나가 안전 경로를
끌 수 있다. **(4) 복귀는 20%(경고)에서 발동한다.** 10% 는 2S 팩의 절벽 구간이라
거기서 출발하면 도크까지 못 갈 수 있고, 전류 센싱이 없어 에너지 예산을 계산할
수단도 없다. 계산된 틀린 값보다 정직한 고정 임계가 낫다.

**Consequences:** 감지 방식(LiDAR 반사판 / IR 비콘 / 카메라 태그)은 **정하지
않았다.** 카메라가 실기 드라이버를 갖느냐에 달렸고 그것은 별도 스펙이라,
`DockDetector` 플러그인 경계 뒤로 유보했다. 경계 위의 코드는 스캔·이미지·IR 을
일절 보지 않고 상대 포즈만 소비하므로, 결정이 나면 플러그인만 교체된다. 구현은
로봇당 도크 1개를 목표로 하되 스키마와 API 는 풀 형태(기종/개체 분리)로 고정해
두었다 — 예약·점유 중재는 Fleet 사안이라 실물 2대 없이 설계하지 않는다.
`DOCK_FAILED` 는 종착이며 스스로 재시도하지 않는다: 무인으로 반복 실패하는
로봇은 물리적 문제를 갖고 있고 자동 루프는 그것을 숨기면서 지키려던 팩을 마저
비운다. 코스트맵 충돌 면제는 접근 구간 전용이며 모든 퇴출 경로가 같은 해제를
지난다. 그리고 `DockState` 는 계약의 `DOCK/UNDOCK/...` 을 다듬어 "도크에 있지
않다"(`UNDOCKED`)와 행위/결과 구분을 추가했다 — enum 값 추가이므로 PRT-006
MINOR 상향이다. 설계 근거는
`docs/plans/2026-09-02-docking-station-design.md` 에 있다.

## D-30 현장 설정은 로컬 오버레이에만 쓰고, 토큰은 해시로만 남긴다

**Status:** Accepted (2026-09-06)

**Context:** 커미셔닝 설정(로봇 id·이름, API 토큰, SAF-004 속도 한계, SAF-005
배터리 임계, fleet 손실 정책)을 바꾸려면 지금까지 SSH 로 들어가 YAML 을 고쳐야
했다. 대시보드에서 바꾸게 하려면 두 가지를 먼저 정해야 한다. **어디에 쓰는가** —
설정 병합 순서는 `rosy_default.yaml` → `~/.rosy/rosy.yaml` → `ROSY_CONFIG` 이고,
패키지 기본값에 쓰면 다음 이미지에서 사라지는 데다 운영자 값이 릴리스 산출물에
섞인다. **토큰을 어떻게 다루는가** — SEC-101 은 정적 토큰 3롤을 규정하지만
저장 형태를 말하지 않았고, 실제 구현은 평문이었다. 평문 토큰을 쓰는 API 를
열면 노출면이 SSH 가능자에서 관리자 세션 전체로 넓어진다.

**Decision:** **(1) 쓰기는 오버레이에만 한다.** `patch_local_config` 가
`ROSY_CONFIG` 가 가리키는 파일(없으면 `~/.rosy/rosy.yaml`)에 deep-merge 하고,
패키지 기본 경로가 대상이면 거부한다. 임시 파일에 쓴 뒤 `os.replace` 로 바꿔,
쓰다 죽어도 반쯤 파싱되는 설정이 남지 않는다. **(2) 토큰은 sha256 다이제스트로만
보관한다.** 인증은 제시된 토큰을 해시해 `hmac.compare_digest` 로 비교한다.
**(3) 토큰을 가리키는 이름은 원문에서 유도하지 않은 불투명 `id` 다.** 처음에는
`sha256(token)[:12]` 를 fingerprint 로 썼는데, 그 값 자체가 약한 토큰을 확인해
보는 오라클이라 해시 저장의 이득을 지운다. 마스킹된 `hint`(앞 3자 + 뒤 2자)도
같은 이유로 없앴다. 대신 운영자가 붙이는 `label` 로 구분한다. **(4) 기본은 서버
생성이다.** `token` 없이 POST 하면 `secrets.token_urlsafe(32)` 를 만들어 응답에
한 번만 싣는다. 직접 정하는 경우는 16자 이상을 요구한다. **(5) 평문 항목은
계속 인증되지만 다음 쓰기에서 해시로 옮겨간다** — 패키지 기본값의 dev 토큰이
그렇고, 목록에 `legacy: true` 로 표시된다.

**Consequences:** 토큰 원문은 생성 응답 한 곳에서만 나간다. 다시 볼 수 없으므로
분실은 재발급이며, 이는 의도된 성질이다. Host Agent 로 넘기던 `user_id` 는
`auth.token[:8]` — 토큰 앞 8자 — 이었고 호스트 감사 로그에 그대로 남았다.
`token_id` 로 바꿨다. `AuthContext` 는 원문을 아예 들고 있지 않아, 앞으로 이
경로로 비밀이 새려면 코드를 되돌려야 한다. 해시는 salt 없는 sha256 이다:
토큰이 고엔트로피 난수라는 전제 위에 서 있고, 그래서 (4)의 생성 기본값과 16자
하한이 장식이 아니라 이 결정의 일부다. 오버레이가 유일한 쓰기 대상이므로
`ROSY_CONFIG` 를 읽기 전용 경로로 지정한 배포는 설정 쓰기가 500 으로 실패하며,
이는 조용히 메모리에만 반영하는 것보다 낫다 — 쓰기가 실패하면 프로세스 상태도
바꾸지 않는다. 남는 구멍 하나: 아직 평문인 항목은 `id` 를 저장할 곳이 없어
`sha256(token)[:12]` 을 쓴다. 재시작 간에 안정된 이름이 필요하기 때문이고, 그
항목은 이미 같은 파일에 평문으로 있으므로 새로 여는 노출은 없다. 첫 쓰기에서
난수 `id` 로 옮겨간다.


## D-31 군집 참조 스트림은 로봇의 소켓이다 — Fleet 은 선택적 중계자

**Status:** Accepted (2026-09-06) — D-20/D-21 구현 결정

**Context:** D-20 은 추종 계산을 로봇에 두고 Fleet 에는 지정·릴레이만 남겼고,
API Ref §7.8 은 그 릴레이 경로를 **Leader → Fleet → Follower** 로 적었다. 그런데
이 리포에는 Fleet 서버가 없고 아웃바운드는 hold 다. 그대로 구현하면 아무도
구동할 수 없는 기능이 생긴다 — 지금까지 swarm 이 "스키마와 우선순위 슬롯은
있는데 라우트는 없는" 상태로 남아 있던 이유이기도 하다. 동시에 CAP-001 은
`swarm.follow: true` 를 광고하고 있었으므로, 계약을 읽은 Fleet 은 404 를 받는다.

**Decision:** **참조 스트림의 양 끝을 로봇에 둔다.** 리더는
`WS /ws/swarm/pose` 로 자기 pose 를 ≥10 Hz 발행하고(SWM-003), 팔로워는
`WS /ws/swarm/reference` 로 참조 pose 를 받는다. 둘은 §7.8 envelope 을 그대로
쓰므로 **리더의 출력을 팔로워의 입력에 바로 물릴 수 있다.** Fleet 이 생기면
가운데 서서 같은 envelope 을 중계하고, 어느 쪽 끝도 바뀌지 않는다 — 이것이
SWM-007 이 요구한 "소비자는 소스를 묻지 않는다"의 실체다. `SwarmManager` 는
전송 계층을 하나도 import 하지 않으며, 테스트가 import 그래프로 그것을 확인한다.

`peer` 소스(D-21)는 **거부한다.** 파라미터는 계약에 있지만 P2P 릴레이가 없고,
받아들인 뒤 조용히 fleet 처럼 처리하면 계약이 거짓말이 된다.

**Consequences:** Fleet 없이 2대로 군집을 검증할 수 있다. 로봇 API 에 인바운드
스트림이 하나 늘었으므로 그 값은 operator 이상이어야 한다 — pose 를 밀어넣는
것은 로봇을 움직이는 일이다. 프레임 하나가 망가져도 소켓을 닫지 않는다: 닫으면
표본 하나가 대형 전체를 HOLD 로 떨어뜨리고, 스트림이 정말 죽었다면 그것을
알아채는 것은 디코딩 실패가 아니라 SWM-004 의 타임아웃이어야 한다.

**남은 한계 — `max_speed`:** SWM-002 의 `max_speed` 는 SAF-004 상한을 넘으면
400 으로 거부하지만, **v1 에서 Nav2 파라미터로 내려가지는 않는다.** CORE 에는
Nav2 파라미터 클라이언트가 없고, 추종은 별도 cmd_vel 소스가 아니라 moving goal
이라(SWM-001) 속도를 CORE 가 직접 클리핑할 지점이 없다. 그래서 실제 주행 속도를
정하는 것은 프로필 상한과 Nav2 설정이며, `max_speed` 는 그보다 낮은 값을
요청했다는 기록으로 남는다. 조용히 무시하는 대신 계약에 그렇게 적었다. 파라미터
클라이언트를 붙이는 것은 별도 작업이다.

**갱신 주기:** 목표는 ≤2 Hz 로 제한한다(SWM-002). 10 Hz 스트림을 그대로 흘리면
Nav2 플래너가 계속 재시작하고, 군집 속도(≤0.2 m/s)에서 2 Hz 면 충분하다. 창
안에 들어온 표본은 버리지 않고 들고 있다가 다음 창에서 낸다 — 버리면 리더의
최신 위치를 잃는다.

**목표에 세대를 붙인다.** moving goal 은 "Nav2 목표는 한 번에 하나이고 임자는
`goal()` 을 부른 쪽"이라는 전제를 깬다. 선점된 목표는 abort 로 끝나고 그 결과가
뒤늦게 도착하는데, 그것을 현재 목표의 실패로 읽으면 `nav_state` 가 FAILED 로
떨어져 이어지는 HOLD 의 취소가 통째로 무시된다 — 스트림이 끊겼는데 로봇이 계속
달린다. `bridge/goal_tracker.py` 가 세대를 매기고 **살아 있는 핸들 전부**를
들고 있으며, 지난 세대의 수락은 등록하지 않고 즉시 취소한다(send 와 accept
사이의 취소 창). 추종 세션 중에는 단발 `POST /navigation/goal` 을 409 로
거절한다: 0.5 초 뒤 스트림에 조용히 덮이느니 거절이 낫다. NAV-006 stuck 기준점도
목표 교체마다 초기화하지 않는다 — 그러면 30 초 무진척 조건이 영원히 성립하지
않아, 문틀에 낀 팔로워가 아무 신호 없이 계속 밀어붙인다.

**추종은 언제 끝나는가.** 세션을 닫는 길은 하나가 아니다 — 운영자의
`/swarm/cancel`, `/navigation/cancel`, MANUAL 전환, e-stop, NAV-006 stuck.
그래서 `NavigationManager` 가 세션이 닫힐 때 임자에게 알리고, 추종은 거기서
끝난다. 알리지 않으면 추종은 목표를 하나도 내지 못하면서 스냅샷에는
`active: true` 로 남는다 — 참조 프레임이 계속 도착하니 스트림도 신선해 보이고
HOLD 도 걸리지 않아, 대형이 멀쩡해 보이는 채로 아무 일도 하지 않는다. e-stop 은 중단이 아니라 **해제**다 — 해제 뒤 참조 프레임
하나로 다시 달리기 시작하면 안 되고, 운영자가 다시 명령해야 한다. stuck 도
같다: SRS 가 "자동 재시도는 하지 않는다"고 못박았는데, 세션을 살려 두면 0.5 초
뒤 스트림이 목표를 다시 밀어넣고 그것이 곧 자동 재시도다(끼인 로봇이 분당 수백
개의 `nav.stuck` 을 감사 로그에 쌓으며 계속 민다). e-stop 은 `SafetyManager` 의
리스너로 붙는다 — API·배터리 어느 경로로 들어오든 같은 자리를 지나기 때문이다.

**도킹에는 양보한다.** DOCKING(4) > NAVIGATION(5) 이고 둘이 같은 Nav2 액션을
쓰므로, 양보하지 않으면 추종이 SAF-005 저배터리 복귀 주행을 계속 선점한다.
양보는 **문 앞에서** 한다 — 받아들인 뒤 다음 틱에 조용히 푸는 것은 거절보다
나쁘다(운영자는 200 을 보고, 로봇은 충전기 위에서 NAVIGATION 에 남는다).
다투는 상태는 `DOCKING`·`UNDOCKING` 뿐이다: `DOCKED`·`CHARGING` 은 주차
상태이고 `DOCK_FAILED` 는 설계상 종착이라, 그것까지 막으면 도킹 실패 한 번이
군집을 영구히 비활성화한다.

**세션 토큰.** 목표에도 취소에도 `NavigationManager` 가 발급한 세션 토큰이 붙는다.
취소가 세션을 닫으면 뒤늦게 도착한 목표는 저쪽 락 안에서 버려지므로, 추종자가
자기 락을 쥔 채 항법을 부를 필요가 없다(락 두 개를 겹쳐 잡지 않는다). HOLD 는
목표만 거두고 세션은 닫지 않는다 — 그래야 돌아온 스트림이 새 follow 명령 없이
이어지고, HOLD 중에도 목표의 임자는 여전히 추종 세션이다. 취소도 같은 규칙을
따른다: 임자가 자기 락을 놓은 사이에 운영자가 대형을 다시 걸었다면 그 새 세션은
남의 것이므로 닫지 않는다. 세션을 여는 것과 무장은 한 구간에서 한다 — 락 밖에서
열면 그 사이에 도착한 취소가 임자 없는 세션을 남기고, 단발 목표가 영영 거절당한다.

**남은 한계 — 맵 일치 확인이 없다.** §7.8 envelope 에는 `map_id` 가 없어서 참조
pose 가 나와 같은 맵의 좌표인지 확인할 방법이 없다. 웨이포인트에는 MAP-002
가드가 있지만(`resolve_goal` 의 MAP_MISMATCH) 여기에는 없고, 다른 맵의 리더를
따라가면 그럴듯해 보이는 엉뚱한 좌표로 간다. envelope 에 `map_id` 를 더하는
것은 계약 변경이라 별도 항목으로 남긴다.

---

## D-32 광고한 능력을 못 지키면 200 이 아니라 코드로 실패한다

**Status:** Accepted (2026-09-06) — CAP-003 준수 수정, D-31 과 같은 결함형

**Context:** `POST /api/v1/slam/reset` 은 `{"reset": true}` 와 200 을 돌려주면서
아무 일도 하지 않았다. 두 경로가 독립적으로 거짓말했다. 맵핑 세션이 없으면
매니저가 조용히 되돌아갔고, 실행기 호출은
`hasattr(self.executor, "reset_mapping")` 뒤에 있었는데 `RosBridge` 에는 그
메서드가 아예 없어서 탐지가 실패하고 호출이 건너뛰어졌다. 그런데 CAP-001 은
`slam: true` 를 광고하므로 능력 게이트는 통과한다 — 계약을 읽은 Fleet 은
리셋을 요청하고, 됐다는 답을 받고, 아무 일도 일어나지 않는다.

D-31 이 며칠 전에 고친 것과 같은 형태다. 그때는 `swarm.follow: true` 를
광고하면서 라우트가 404 였고, 지금은 `slam: true` 를 광고하면서 라우트가
거짓 200 이다. 404 는 최소한 정직하다.

**Decision:** **능력을 광고했는데 런타임이 못 지키면 명확한 에러 코드로
실패한다.** CORE SRS CAP-003 이 "일반 실패가 아닌 명확한 에러 코드"를 요구하고,
DNC-003 이 미지원 도킹에 이미 501 `CAPABILITY_NOT_SUPPORTED` 를 쓰고 있으므로
새 규약이 아니라 기존 규약의 적용이다.

세 가지가 따라온다. 첫째, **계약에 없는 멤버를 `hasattr` 로 더듬지 않는다.**
`NavExecutor` 가 `reset_mapping` 을 선언하고, `RosBridge` 가 구현하되 실물
slam_toolbox `Reset` 이 붙기 전까지는 `CAPABILITY_NOT_SUPPORTED` 로 실패한다.
Protocol 은 구조적이고 `RosBridge` 는 베이스 클래스를 선언하지 않으므로 이
선언은 런타임을 구속하지 않는다 — 문서이지 강제가 아니며, 그래서 테스트
페이크 일곱 개는 하나도 고칠 필요가 없었다. 둘째, **능력 답변이 세션 답변보다
먼저 온다.** 실행기가 없으면 501, 있는데 세션이 없으면 400. 순서를 뒤집으면
"이 런타임은 그걸 못 한다"가 400 으로 나가 계약이 틀린다. 셋째, **엔드포인트는
건드리지 않는다.** `api/errors.py` 가 이미 `NavigationError` 를 `_HTTP_BY_CODE`
로 태우므로 501·400 이 기존 핸들러에서 떨어진다. `slam/save` 의
`except RuntimeError` 모양은 일부러 복사하지 않았다 — 다른 예외 계열을 잡고,
서비스 실패를 `CAPABILITY_NOT_SUPPORTED` 로 접는 혼동을 두 번째 엔드포인트로
퍼뜨린다.

**Consequences:** **API-002 의 의미 변경이 아니라 CAP-003 위반의 시정이다.**
200 쪽이 위반이었다. 그래도 응답이 바뀌므로 API Ref 는 v1.7 로 올리고 해당
행에 501 조건을 적는다 — D-31 이 v1.6 에서 한 것과 같은 절차다.

**비파괴로 만드는 것은 D-31 유비가 아니라 blast radius 다.** D-31 은 404 를 동작하는 라우트로 바꿨으니 가산적이고 어떤 소비자도 깨질 수 없었다. 여기는 200 을 에러로 바꾸므로 `response.ok` 로 분기하는 소비자는 깨질 수 있다 — 둘 중 깨질 수 있는 쪽은 이쪽뿐이다. D-31 은 *어떻게 버전을 올리는가*의 선례이지 *왜 파괴적이지 않은가*의 근거가 아니다. 근거는 실측이다: 배포 오버레이 셋이 모두 `slam: false` 이므로 현장에서는 이미 능력 게이트가 501 로 막고 있었고, 거짓 200 은 패키지 기본 설정에서만 도달 가능했다.

소비자 영향은 0 이다. 대시보드는 `slam/start`·`stop`·`save` 만 호출하고
(`web/settings.js`), `fleet_agent/` 에는 slam 참조가 없다. Flask 패리티 E-6 은
"API 완료"에서 **hollow** 로 강등한다 — 체크리스트가 실제보다 앞서 있었다.

실물 리셋(slam_toolbox `Reset` 서비스, 이식원
`rosy_navigation/scripts/nav2_web_server.py`)은 **여기서 구현하지 않는다.**
배포 오버레이 셋이 모두 `slam: false` 이고 CI 에도 slam_toolbox 가 없어서 오늘
어디서도 검증할 수 없다. `mapping/` 패키지 재진입 트리거에 함께 걸어 둔다
(`docs/plans/2026-09-06-module-split-criteria.md`). 그때 리셋이 어떤 이벤트를
발행할지도 함께 정해야 한다 — 지금은 두 경로가 모두 먼저 raise 하므로 기존
`slam.started {"reset": true}` 발행은 도달 불가 코드로 남아 있다.

---

## D-33 로봇 신원은 하나의 로봇 번호에서 나온다

**Status:** Accepted (2026-09-06) — D-6 대체

**Context:** D-6 은 "로봇별 고유 `ROS_DOMAIN_ID`" 를 결정했지만, 구현은 그 결정을
지키지 않았다. `deploy/robot/.env.example` 이 `ROS_DOMAIN_ID=42` 와
`ROSY_NAMESPACE=rosy_01` 을 **값으로** 들고 있었고, `install-pi.sh` 는 그 템플릿을
그대로 복사한다. 그래서 릴리스에서 설치된 모든 기기가 같은 도메인 **그리고** 같은
네임스페이스로 출고됐다 — 도메인만 겹친 것이 아니라 토픽 이름까지 전부 겹쳤다.
개발용 `rosy_env.sh` 는 `40 + N` 이라는 또 다른 규칙을 쓰고 있어서, 스크립트로 띄운
2호기가 기본 배포된 모든 기기와 정확히 충돌했다.

이 결함은 설치 스크립트만 고쳐서는 사라지지 않는다. 값을 채워 넣는 헬퍼
(`set_env_default`) 는 키가 **없을 때만** 쓰므로, 템플릿이 값을 들고 있는 한 영영
발화하지 못한다. 계획 검토 중 이 함정을 두 번 밟았다: 두 번 다 호출은 추가됐고
테스트는 초록이었으며 기기는 여전히 충돌했다.

**Decision:** 로봇 신원은 **로봇 번호 하나**에서 유도한다 — `ROS_DOMAIN_ID = 40 + N`,
`ROSY_NAMESPACE = rosy_%02d`. 그리고 세 계층 모두에서 **기본값을 없앤다**:

- `.env.example` 은 두 키를 **배정하지 않는다** (규칙만 주석으로 남긴다).
- `install-pi.sh` 는 `ROSY_ROBOT_NUMBER` 를 **요구**하고, `0 <= 40+N <= 101` 을
  검증하며, 이미 다른 번호로 자리잡은 기기를 만나면 **두 값을 모두 이름 대어 실패**한다.
- `compose.yaml` 은 여섯 군데 전부 `${VAR:?...}` 를 쓴다 — `:8` 만 고치면 반쪽이다.
  `:51` 이 실제로 노드가 기동에 쓰는 `__ns:=` 인자다.

검증은 "호출이 있는가" 가 아니라 **"신규 설치가 실제로 다른 값을 낳는가"** 로 한다
(`test/test_dds_identity_contracts.py`).

**Consequences:** 신원 미설정은 조용한 충돌이 아니라 기동 실패가 된다 — 의도한 바다.
이미 배포된 기기는 자동으로 재번호되지 않으며, 다음 프로비저닝 때 불일치 검사가
잡는다. 재번호 절차는 `docs/deployment/raspberry-pi-runtime.md` 에 있다.
D-6 의 localhost-only 프로파일 결정은 **그대로 유효하다** — 이 ADR 은 신원 유도만
대체한다.

---

## D-34 발행 주기는 그것을 읽는 쪽에 맞춘다

**Status:** Accepted (2026-09-06)

**Context:** global costmap 은 `publish_frequency: 1.0` 으로 전체 격자를 초당 한 번씩
내보내고 있었다. 그런데 그 격자를 읽는 유일한 소비자는 대시보드이고,
`src/rosy_core/rosy_core/web/app.js:647` 의 `refreshSlowData` 는 **5000 ms 간격**이다.
게다가 스트림이 아니라 캐시에 대한 REST pull 이라, 브라우저가 하나도 열려 있지
않아도 초당 한 장씩 계속 나갔다. 즉 소비자보다 다섯 배 빨랐다.

`publish_voxel_map: True` 는 더 단순한 경우다 — 저장소 전체에서 구독자가 하나도
없다. RViz 디버그 출력인데 `update_frequency: 5.0` 에 물려 있어서, 아무도 보지 않는
격자를 초당 다섯 번 내보내고 있었다.

이 값들에는 어떤 테스트도 걸려 있지 않았다. `publish_frequency` 를 grep 하면 params
파일 자신 말고는 나오지 않는다.

**Decision:** **발행 주기는 측정이 아니라 소비자에게서 읽는다.** 두 costmap 의
`publish_frequency` 를 `0.2` 로, `publish_voxel_map` 을 `False` 로 둔다. 숫자의 출처는
`app.js:647` 의 폴링 간격이며, 그 간격이 바뀌면 이 값도 함께 바뀐다.
`test/test_nav2_bandwidth_contracts.py` 가 둘의 관계를 고정한다.

플래너 품질은 `update_frequency` 가 정하므로 이 변경은 항법 거동과 무관하다.

**Consequences:** 최악의 경우 맵 패널이 약 10초까지 낡을 수 있다. **이것이 너무
낡다고 판단되면 주기를 다시 올리는 것이 아니라 수요 기반 충전으로 간다** — 캐시를
채우는 주체를 타이머에서 요청으로 바꾸는 쪽이다. 그것이 **잠정적인 장기 방향**이며,
`maps.py` / `api/v1/map.py` 의 모듈 소유권 판정
(`docs/plans/2026-09-06-module-split-criteria.md`)에 걸려 미뤄져 있다.

이 ADR 은 주기적 push 를 결정된 구조로 승인하지 않는다. 지금의 주기는 현재 소비자에
맞춘 값일 뿐이고, 소비자가 사라지면 그 값도 0 이 되는 것이 옳다.
RViz 사용자는 `publish_voxel_map` 을 로컬에서만 되살린다 — 배포본에는 켜서 보내지 않는다.
