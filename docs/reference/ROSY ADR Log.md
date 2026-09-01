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
| D-6 | 로봇 간 DDS 차단 (도메인 격리) | Accepted |
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
| D-19 | 접속 토폴로지: 로봇 WiFi 릴레이(AP+STA) 지원 | Accepted |
| D-20 | Swarm 하이브리드: 오케스트레이션 Fleet / 폐루프 추종 로봇 탑재 | Accepted (D-12 확장) |
| D-21 | 군집 제어: 계층형 마스터-슬레이브 확정 + 분산 진화 훅 | Accepted (D-20 보강) |
| D-22 | Raspberry Pi OS 런타임: Core/I/O 컨테이너 분리 + 드라이버 deadman | Accepted |

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

**Status:** Accepted (2026-08)

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

**Status:** Accepted (2026-08-29)

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
