# 신호등 컨트롤러(ESP32 + Wi-Fi) 조사 보고서

- **문서 ID:** ROSY-SIGNAL-R001 (연구 보고서, 계약 아님)
- **Status:** 조사 완료 / 설계 전 — 이 문서는 근거를 모은 것이지 계약이 아니다
- **Date:** 2026-09-21
- **Related:** `dock/README.md` (ROSY-DOCK-001 선례),
  `docs/plans/2026-09-14-site-middleware-role-fabric-design.md` (D-59),
  `src/site/fleet/fleet/server/AGENTS.md` (Fleet 콘솔 v1)

## 1. 배경과 목적

알리익스프레스에서 구입한 LED 신호등은 **접점 스위치(드라이 콘택트)로 켜고 끄는** 제품이다.
스위치 접점이 닫히면 해당 색이 켜진다. 이 신호등을 그대로 두고, 접점을 사람 손 대신
ESP32 + 릴레이로 대신 닫아 주면 **관제(Fleet 콘솔)에서 신호등을 제어**할 수 있다.

로지(Rosy) 쪽 니즈와의 연결:

- Fleet 는 이미 "교행은 Fleet 만 볼 수 있다" — 두 경로를 동시에 쥔 쪽이 Fleet 이고
  여기서 순서를 정한다(`traffic.py`, D-12). 신호등은 그 **순서 판정을 물리적으로
  보여 주는 현장 장비**가 된다.
- 관제 UI(`fleet/server/`)에서 N대의 목표·취소·전체 정지를 내리듯, 사이트 신호등의
  패턴(수동/자동/전체 정지)도 같은 화면에서 내린다.
- 로봇 경기(`rosy_games`)나 시연에서 출발·정지 신호로 쓴다.

이 보고서는 (a) 대상 신호등 제품군, (b) 접점 구동부(릴레이), (c) ESP32 하드웨어,
(d) 펌웨어 스택, (e) 통신 구조, (f) 안전 설계, (g) ROSY 통합 구조를 조사하고
권장안을 제시한다.

## 2. 요약 — 권장 구성

| 항목 | 권장안 | 근거 |
|---|---|---|
| 신호등 | DC 12/24V 제품 (AC 제품보다 저압 우선), 100–200mm | 실내 사이트, 절연 부담 최소화 (§3) |
| 접점 구동 | 옵토커플러 절연 기계식 릴레이 모듈 (SPDT, 10A 250VAC/30VDC) 3.3V 트리거 호환 | SSR(G3MB 계열)은 AC 전용이라 DC 접점 스위칭에 부적합 (§4) |
| MCU | ESP32-DevKitC (WROOM-32E) 또는 ESP32-S3-DevKitC-1 | GPIO 여유, 독 펌웨어와 동일 Arduino core 계열 (§5) |
| 채널 산정 | 신호기 1개 = R/Y/G 3채널. 2개 신호기 + 여유 = 8채널 릴레이 1장 | §5.3 |
| 펌웨어 | 자체 Arduino 스케치 (독 선례: WebServer + Preferences/NVS) + heartbeat 페일세이프 | `dock/firmware` 와 스택 일치 (§6) |
| 통신 | Fleet 서버 ↔ ESP32: LAN 안 HTTP(명령/상태) + 폴링 heartbeat. MQTT는 선택 | 독 선례(폴링, 장치가 연결을 열지 않음)와 정합 (§7) |
| 페일세이프 | heartbeat 끊기면 **전체 적색 점멸**(또는 황색 점멸). 부팅 직후도 동일 | EN 12675 / 충돌 모니터 관행의 원칙 차용 (§8) |
| 명령 주체 | Fleet 서버 단일. 로봇 CORE 는 신호등을 모른다 | D-59 site fabric (§9) |
| 인증 | 명령 엔드포인트에 토큰 필수 (독은 read-only 여서 무인증이었으나 신호등은 actuation) | `dock/AGENTS.md` "Adding actuation requires revisiting auth" (§9) |

## 3. 대상 하드웨어 — 알리 신호등 제품군

중국발 LED 신호등 모듈은 아래 축으로 판매된다(Alibaba/DHgate/AliExpress 리스팅 공통):

| 축 | 옵션 |
|---|---|
| 렌즈 지름 | 52 / 82 / 88 / 100 / 125 / 170 / 200 / 300 mm |
| 전압 | **DC 12V / DC 24V / AC 85–265V** |
| 색 구성 | 적/황/녹 풀볼, 적십자-녹색화살, 보행자(적록), 카운트다운 타이머 포함형 |
| 하우징 | PC(폴리카보네이트), 방수 등급 IP65 표기 다수 |
| 가격대(참고) | 300mm 모듈 ~US$35, 100mm 적록 stop-go AC형 ~US$49–53, 300mm 보행자 카운트다운 ~US$124–130 (2026-09 리스팅 기준, 변동 큼) |

### 3.1 접점 스위치 방식이란

이 제품들은 전원 라인 + 색별 라인(또는 공통단자 + 색별 단자)으로 구성되고, 판매 시
딸려오는 벽부 스위치/리모컨 수신기의 **릴레이 접점이 색별 라인을 전원에 연결**하는
구조다. 즉 "접점이 닫히면 그 색이 켜진다". 우리가 만들 컨트롤러는 이 접점을
ESP32가 제어하는 릴레이로 대체하는 것 — 기존 수동 스위치는 그대로 두고 릴레이 NO
접점을 **병렬**로 붙이면 수동 운영과 자동 제어가 공존한다.

### 3.2 구입 시 결정 사항

- **전압: DC 12V 또는 DC 24V 권장.** AC 85–265V 제품은 메인스 절연(인클로저, 퓨즈,
  크리피지) 설계가 따로 필요하다. 실내 로봇 사이트라면 저압 DC 한 세트(PSU + 릴레이
  접점)가 안전하고 부품도 단순하다.
- **크기:** 실내 시연·경기 기준 100–200mm 면 충분. 300mm는 야외/원거리 가시성용.
- **배선 확인:** 주문 전 "common anode/cathode 여부, 색별 리드 수, 정격 전류"를
  문의할 것. LED 모듈은 색당 통상 수십~수백 mA 수준이라 릴레이 정격(10A)에는
  여유가 크지만, 실측이 원칙이다.

## 4. 접점 구동부 — 릴레이 선택

### 4.1 기계식 릴레이 모듈 (권장)

- 대표 부품: Songle **SRD-XXVDC-SL-C** 계열 (SPDT, 정격 10A 250VAC / 10A 30VDC,
  전기적 수명 ~10만 회). 이것을 얹은 옵토커플러 절연 모듈이 1/2/4/8채널로 널리 판매된다.
- **3.3V 트리거 주의:** ESP32 GPIO는 3.3V다. 모듈 대부분이 "high/low level trigger
  점퍼 + 3.3V 호환"을 내세우지만, 5V 입력 전용 옵토커플러 입출력 저항이 들어간 저가
  모듈은 3.3V에서 불안정하게 접도 된다. **3.3V 동작을 명시한 모듈**(예: Elecbee 3.3V
  low-level trigger, PC817 옵토커플러)을 고르거나, 트랜지스터 1단(예: S8050)으로
  구동한다.
- 모듈에는 통상 플라이백 다이오드가 포함된다. 별도 베어 릴레이를 쓰면 다이오드를
  반드시 코일에 병렬로 넣는다.
- 릴레이 코일 전원은 MCU와 **분리한 전원**(또는 분리 레일)에서 공급하고, 접지는
  한 점에서만 공통으로 — 접점 개폐 순간의 전원 노이즈로 ESP32가 리셋되는 사례가
  흔하다.

### 4.2 SSR(솔리드 스테이트 릴레이) — 이 용도에는 부적합

널리 쓰는 Omron **G3MB-202P** 는 2A 100–240VAC **AC 전용** phototriac 출력이다.
DC 부하 스위칭이 불가하고(데이터시트 명시), OFF 시 누설 전류 ~1.5mA@200VAC 가
흐른다. AC 신호등 제품을 AC 메인으로 구동할 경우에만 후보가 되며, 그때도 정격의
20–30% 디레이팅과 방열이 필요하다. 우리 권장안(DC 저압)에서는 기계식 릴레이가 답이다.

### 4.3 절과 안전

- 옵토커플러 절연 모듈을 쓰면 제어측(ESP32)과 부하측(신호등 전원)이 전기적으로 분리된다.
- AC 제품을 쓸 경우에만: 금속 인클로저 접지, 퓨즈, 단자 크리피지 확보. DC 12/24V면
  일반 실내 배선 수준이면 충분하다.

## 5. ESP32 하드웨어

### 5.1 보드 비교

| 보드 | 특징 | 비고 |
|---|---|---|
| ESP32-DevKitC (WROOM-32E) | 듀얼코어 LX6, Wi-Fi+BT, 다수 GPIO, 최저가 | 독 펌웨어와 동일 계열 — 재료·노하우 공유 |
| ESP32-S3-DevKitC-1 | 듀얼코어 LX7, native USB, GPIO 45개 | strapping: GPIO0/3/45/46. Octal PSRAM 변형은 GPIO35–37 내부 사용 |
| ESP32-C3-DevKitC-02 | 싱글코어 RISC-V, 저가·소형 | strapping: GPIO2/8/9. GPIO 수가 적어 릴레이 8채널+입력에는 빠듯 |

채널 수(GPIO 8개 + 수동 오버라이드 입력 1–2개 + 여유)를 보면 WROOM-32E 또는 S3 가
적절하다. **독(`dock/firmware`)이 ESP32 Arduino core(WiFi, WebServer, Preferences/NVS)
이라는 점이 결정적** — 같은 스택을 쓰면 빌드 환경과 펌웨어 규칙(자격증명 소스 금지,
NVS 저장)을 그대로 재사용한다.

### 5.2 통합 릴레이 보드 (대안)

직접 배선 대신 ESP32+릴레이가 합체된 제품도 옵션이다: KinCony KC868 시리즈(A2~A16,
ESP32-S3 기반 2~16채널, ESPHome/Tasmota/MQTT/HTTP 지원, 알리에서 판매). 채널당 릴레이
정격·옵토 절연·하우징이 갖춰져 공수가 줄지만, 펌웨어를 우리 규칙으로 완전히 쥐려면
커스텀 스케치를 얹는 확인 작업이 필요하다. 벤치 1단계에서는 범용 DevKitC + 8채널
릴레이 모듈, 2단계에서 제품화 판단을 권한다.

### 5.3 채널 산정 예

```
신호기 2개 × (적/황/녹 3채널) = 6
보행자/화살표 확장 여유      = 2
------------------------------
소계 8채널 → 8CH 릴레이 모듈 1장
```

### 5.4 전원

- ESP32: 5V (USB 또는 DIN레일 PSU의 5V 레일). 브라운아웃 감지 내장.
- 릴레이 코일: 5V 또는 12V (모듈 사양). ESP32와 같은 PSU를 쓰더라도 코일 전류가
  순간 수백 mA — 디커플링 콘덴서와 분리 레일 권장.
- 신호등: DC 12V/24V 제품이면 PSU 전압 일치. 케이블 길이(전압 강하) 감안.

## 6. 펌웨어 스택 비교

| 스택 | 장점 | 단점 | 판단 |
|---|---|---|---|
| **ESP32 Arduino core (PlatformIO/Arduino IDE)** | 독 펌웨어와 동일. WebServer/Preferences 그대로 | 메뉴컨피그 등 세부 제어 약함 | **채택** — 자산 재사용 |
| ESPHome | YAML 선언형, OTA·API 내장, HA 연동 | Fleet 연동은 결국 커스텀 컴포넌트 필요. 관제 스택(HA 아님)과 안 맞음 | 대안. 통합 릴레이 보드(KinCony) 쓸 때만 재검토 |
| ESP-IDF | 공식 SDK, 세부 제어(brownout, sdkconfig), ESPHome도 IDF 기본 권장 | 학습·보일러플레이트 비용 | 이 규모(릴레이 몇 개 + HTTP)엔 과함 |

참고: ESPHome 은 ESP-IDF 를 기본/권장 프레임워크로 안내하고, C2/C5/C6/C61/H2/P4 는
IDF 필수다(§10 참고자료). 우리 선택은 "독과 같은 Arduino core" 이다.

## 7. 통신 구조

| 방식 | 평가 |
|---|---|
| **HTTP REST (Fleet → ESP32 폴링/명령)** | 독 선례(로봇이 독을 폴링, 장치는 연결을 열지 않는다)와 정합. 구현·디버그 가장 단순. 명령은 POST, 상태는 GET |
| WebSocket (상태 푸시) | Fleet 쪽 의존성(websockets)과 맞지만, 신호등 상태는 초당 변하지 않는다 — 폴링으로 충분 |
| MQTT | 브로커 운영이 새로 생긴다. LWT(retained)로 오프라인 감지는 우아하지만, heartbeat 폴링으로도 동일한 안전성 확보 가능. 이미 브로커를 굴리는 날에 재검토 |
| ESP-NOW | 인프라 없이 통신하지만 게이트웨이/범위 제약, 관제 LAN 과 이원화 — 탈락 |

**권장:** Fleet 서버가 각 신호등 컨트롤러를 LAN에서 폴링(heartbeat 겸 상태 수집)하고,
명령은 POST 로 내린다. ESP32 는 **명령을 기억(NVS)하고 heartbeat 타임아웃 시 로컬
페일세이프로 복귀**한다. MQTT LWT 의 "죽으면 브로커가 대신 말해 준다" 패턴
(HiveMQ 문서)은, 여기서는 "Fleet 이 폴링이 끊기면 오프라인으로 보고하고 ESP32 는
스스로 페일세이프"로 동등하게 달성한다.

## 8. 안전 설계 (핵심)

도로용 신호제어기 표준의 **원칙**을 실내 사이트 규모로 차용한다(인증 대상이 아니라
설계 지침으로):

1. **페일세이프 상태를 부팅·단절 공통으로 정의한다.** EN 12675 계열 표준은 녹-녹
   충돌 같은 결함 분류와 "결함 시 점멸(all-flash) 모드"를 요구하고, 실제 제어기는
   충돌 모니터가 결함을 감지하면 점멸 모드로 떨어뜨린다. 우리 정의:
   - 부팅 초기화 전 / heartbeat 단절 / 펌웨어 패닉 → **전 기능 적색 점멸**
     (보행자 없는 로봇 사이트 기준. 황색 점멸로 바꿀 수 있게 상수로만 분리)
   - 명시적 "전체 정지" 명령(`estop` 성격) → **전 기능 적색 점등**
2. **단일 명령 주체.** Fleet 서버만 신호등에 명령한다. 로봇 CORE 는 신호등을 직접
   제어하지 않고, 신호등 상태를 근거로 달리 판단해서도 안 된다 — 신호등은 표시 장치일
   뿐 안전 인터록이 아니다. 로봇의 정지 판단은 기존 안전 체계(e-stop,
   cmd_vel deadman)가 그대로 담당한다.
3. **수동 오버라이드 병렬 접점.** 기존 접점 스위치를 릴레이 접점과 병렬로 남겨
   관제/네트워크가 죽어도 사람이 손으로 켤 수 있게 한다(§3.1).
4. **모순 방지는 ESP32 안에서.** 적+녹 동시 점등 같은 불가능 조합은 펌웨어 state
   machine 이 거절한다(EN 12675 의 충돌 클래스 개념을 몇 줄의 guard 로).
5. **관측 가능성.** 상태 GET 은 현재 점등 조합 + 마지막 명령 출처 + faults 목록을
   독의 `/status` 처럼 돌려준다. 필요하면 전류 측정(독의 `current_a` 선례)을 추가해
   "켜라고 했는데 실제로 켜졌는가"를 전기적 사실로 확인한다.

## 9. ROSY 통합 구조 제안

### 9.1 배치

독 선례를 그대로 따른다 — 계약 README + firmware 폴더:

```
signal/                      # 또는 traffic_signal/
  README.md                  # ROSY-SIGNAL-001: 상태 스키마, 전기/기계, 펌웨어 규칙
  progress.md / logs.md / index.md
  firmware/rosy_signal/rosy_signal.ino
src/site/fleet/fleet/server/ # Fleet 서버에 signals 클라이언트 + 엔드포인트 확장
test/test_signal_contract.py # 독의 test_dock_contract.py 선례
```

site 계층 규칙 유지: `site/` 패키지는 ROS import 가 없다. 신호등은 **계약 버스(HTTP)
로만** Fleet 와 만난다(D-59: 디바이스는 계약 버스만).

### 9.2 계약 초안 (ROSY-SIGNAL-001 후보)

독과 반대로 신호등은 **명령을 받는** 장비다 — 독이 read-only 여서 무인증이었던 것과
다른 점이며, `dock/AGENTS.md` 가 예고한 대로 "actuation 추가는 인증 재검토"가
필요하다.

```
GET  /status              → { signal_id, firmware, mode, lamps:{r,g,b?}, faults:[], heartbeat_sec }
POST /command             → { seq, mode: "manual"|"cycle"|"hold"|"all_red"|"flash_red",
                              lamps?: {r,g,y}, cycle?: {green_sec, yellow_sec, red_sec} }
                            (토큰 필수 — fleet robots.yaml 토큰 패턴, D-30 스타일)
```

- ESP32 는 마지막 유효 명령을 NVS 에 두고, 재부팅 시 **페일세이프 우선** 후 Fleet
  재도달 시 복원.
- Fleet 서버 확장(초안): `GET /api/fleet/signals`, `POST /api/fleet/signals/{id}/command`,
  기존 `/api/fleet/estop` 처리 시 등록된 신호등에 `all_red` 를 scatter. 토큰 가드는
  기존 `dependencies=guard` 패턴 재사용.
- 관제 UI: 신호등 상태 카드 + 수동/사이클/전체정지 버튼 (CSP 규칙 준수 — 클래스로만
  스타일).

### 9.3 명령 신뢰성

독 문서의 태도("시스템이 고장·오배선·다른 장비 교체 상황에서도 성립해야 할 성질")를
그대로 적용한다: Fleet 는 신호등 `/status` 의 `lamps` 보고와 자신이 보낸 마지막
명령을 대조하고, 불일치가 계속되면 UI 에 faults 로 드러낸다. 신호등 보고만으로
로봇 쪽 안전 동작을 억제하는 경로는 만들지 않는다(독의 `charging:true` 단독 불신
원칙과 동일).

## 10. BOM 개요 (벤치 1세트 기준, 가격 변동 큼)

| 항목 | 예시 | 비고 |
|---|---|---|
| 신호등 | WDM 100/200mm R/Y/G DC12V 모듈 ×2 세트 | 접점 방식 확인 후 주문 |
| MCU | ESP32-DevKitC (WROOM-32E) | 독과 동일 계열 |
| 릴레이 | 8CH 옵토커플러 모듈 (3.3V 트리거 확인) | Songle SRD 계열 |
| PSU | 12V DIN PSU (신호등+릴레이) + 5V (ESP32) | 디커플링 포함 |
| 기타 | 인클로저, 단자대, 케이블, (선택) INA219 전류 센서 | 전류 센서는 §8.5 |

## 11. 단계별 진행 제안 (gate: SOURCE→FIELD 준용)

1. **G-S0 SOURCE:** 본 보고서 검토 + 신호등 후보 리스팅 확정(전압/배선 문의).
2. **G-S1 BENCH:** DevKitC + 릴레이 + 신호등 1기 벤치. 접점 개폐 실측, 3.3V 트리거
   확인, 노이즈 리셋 여부 확인. 펌웨어: 페일세이프 state machine + 수동 사이클.
3. **G-S2 CONTRACT:** `signal/README.md` (ROSY-SIGNAL-001) 작성, 계약 시험
   (`test_signal_contract.py`) — 자격증명 소스 금지 검사 포함.
4. **G-S3 INTEGRATION:** Fleet 서버 signals 클라이언트 + 엔드포인트 + UI 카드.
   가짜 신호등(fake HTTP) 만으로 pytest — 네트워크 없이.
5. **G-S4 FIELD:** 실제 LAN 에서 관제 → 신호등 2기 제어. heartbeat 단절 시
   페일세이프 전이 실측, e-stop scatter 연동 확인.

## 12. 미확정 사항 (HOLD)

- 신호등 **개수와 설치 위치**, 신호기당 색 구성(화살표/보행자 포함 여부) — 채널 산정 입력
- 제품 전압(12 vs 24V)과 **실측 소비 전류** — 주문 후 실측
- 관제 LAN 위 토폴로지(신호등 위치의 Wi-Fi 수신 강도, 유선 대안)
- 전류 측정(§8.5)을 v1 에 넣을지 — 독이 전류 측정을 "부차"로 밀어낸 것과 같은 판단 필요
- MQTT 브로커 도입 여부(다른 site 장비가 함께 늘어날 때 재검토)

## 13. 참고 자료

외부(1차 자료 우선):

1. EN 12675:2017 — Traffic signal controllers, functional safety requirements
   (결함 분류·요구 개요): iTeh 카탈로그 https://standards.iteh.ai/catalog/standards/cen/a854c361-71ed-49b6-ba09-a0c27f73a4fb/en-12675-2017
2. TR2500A Traffic Signal Controller Specification (BS EN 12675 결함 클래스, 주결함 시
   all signals off, red lamp monitoring): https://www.traffic-signal-design.com/downloads/tr2500a.pdf
3. Georgia Tech — Mode of Flashing for Malfunctioning Traffic Signals (점멸 모드 관행과
   한계): https://transportation.ce.gatech.edu/arterial-operations/mode-of-flashing-for-malfunctioning-traffic-signals
4. Omron G3MB-202P 데이터시트 (2A 100–240VAC, AC 전용, 누설 1.5mA@200VAC, 서지 30A):
   https://docs.rs-online.com/db5e/0900766b8002f991.pdf
5. Codrey Electronics — SSR Primer (G3MB-202P 구조, 제로크로스, 디레이팅 20–30%):
   https://www.codrey.com/electronic-circuits/solid-state-relay-ssr-primer
6. Songle SRD 계열 정격 예시(10A 250VAC/30VDC, 전기수명 10만 회): Amazon 상품 데이터
   https://www.amazon.com/Channel-Interface-Module-SONGLE-SRD-12VDC-SL-C/dp/B07VYLK74T
7. 3.3V 트리거 옵토커플러 릴레이 모듈 예시(Elecbee, PC817): https://www.elecbee.com/en/product-detail/1-channel-3-3v-relay-module-low-level-trigger-optocoupler-isolation-for-arduino-esp8266-esp32-10a-250v-ac-dc_28712
8. 릴레이 모듈 사용 가이드(별도 전원, 플라이백, 3.3V 주의): Phipps Electronics https://www.phippselectronics.com/support/users-guide-12v-1-channel-relay-module-highlow-trigger-optocoupler
9. 신호등 모듈 제품 사례(WDM 100–300mm, DC12/24V, AC85-265V, IP65): DHgate 리스팅 https://au.dhgate.com/traffic-light-controller-with-remote-australia.html ,
   Made-in-China 가격 예시(300mm ~$35, 100mm stop-go $49–53, 300mm 카운트다운 $124–130):
   https://m.made-in-china.com/amp/product/Clear-Lens-LED-Traffic-Light-Module-12inch-300mm-Green-Color-Roadway-Safety-712385812.html
10. Espressif ESP32-S3-DevKitC-1 핀아웃/strapping(GPIO0/3/45/46, octal PSRAM 시 35–37 불가):
    https://esp32.co.uk/esp32-s3-devkitc-1-pinout-gpio-reference-safe-pins-usb-adc-touch-i%C2%B2c-spi
11. ESP32-C3-DevKitC-02 strapping(GPIO2/8/9), ADC2-Wi-Fi 주의: https://esp32.co.uk/esp32-c3-devkitc-02-pinout-gpio-reference
12. ESPHome ESP32 플랫폼(IDF 기본/권장, C2/C5/C6/C61/H2/P4 필수, NVS 암호화):
    https://esphome.io/components/esp32
13. MQTT LWT + retained (오프라인 감지 패턴): HiveMQ Essentials https://www.hivemq.com/blog/mqtt-essentials-part-9-last-will-and-testament
14. KinCony KC868 시리즈(ESP32-S3 릴레이 보드, ESPHome/Tasmota/MQTT/HTTP):
    https://www.kincony.com/esp32-s3-16-channel-gpio-module.html , https://www.aliexpress.com/item/1005005493267039.html

내부(이 저장소):

- `dock/README.md` — ROSY-DOCK-001: 폴링 방향, 상태 스키마, "장비 보고 단독 불신" 원칙
- `dock/AGENTS.md` — read-only HTTP 원칙, "actuation 추가는 인증 재검토", 자격증명 소스 금지
- `src/site/fleet/fleet/server/AGENTS.md` + `app.py` — 관제 엔드포인트/토큰 가드/UI 규칙
- `docs/plans/2026-09-14-site-middleware-role-fabric-design.md` — D-59: 관제가 모으고
  흩뿌리고, 디바이스는 계약 버스만
- `src/site/fleet/fleet/server/traffic.py` — 교행 판정이 Fleet 소유(D-12)라는 맥락
