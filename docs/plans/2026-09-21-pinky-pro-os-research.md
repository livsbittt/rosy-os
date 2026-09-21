# 핑키프로 공식 OS·소프트웨어 스택 조사

조사일: 2026-09-21. **문서 조사이며 실기 검증이 아니다.** 로봇 부팅, 이미지 굽기, 센서 동작, Nav2 주행을 직접 실행한 결과가 아니다.
1차 소스는 다음 세 가지다. 모든 주장은 이 아래 경로·URL로 역추적할 수 있어야 한다.

- **frozen upstream (최우선)**: `reference/src/pinky_pro-main.zip` — 분석용 해제본: `X:\DevTemp\opencode\pinky-pro-research\pinky_pro-main\`. 인용 표기: `reference/src/pinky_pro-main.zip 내 <경로>`
- **live upstream**: [pinklab-art/pinky_pro](https://github.com/pinklab-art/pinky_pro) main (2026-09-21 기준, 최신 커밋 `014a09f`). 검증용 전체 트리를 [codeload zip](https://codeload.github.com/pinklab-art/pinky_pro/zip/refs/heads/main)으로 내려받아 frozen과 파일 단위 diff했다.
- **공식 Wiki**: [pinklab-art/pinky_study wiki](https://github.com/pinklab-art/pinky_study/wiki) 중 [0. 초기설정(PinkyPro)](https://github.com/pinklab-art/pinky_study/wiki/0.-%EC%B4%88%EA%B8%B0%EC%84%A4%EC%A0%95(PinkyPro)), [2.4 Pinky Pro(part4-실물로봇활용)](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%A1%9C%EB%B4%87%ED%99%9C%EC%9A%A9))

기존 문서와의 분업: 하드웨어·OMX 탑재는 [2026-09-12 핑키프로·OMX 탑재 조사](2026-09-12-pinky-omx-mounting-spec-research.md), OMX 사양은 [2026-09-12 OMX 하드웨어 사양 조사](2026-09-12-omx-hardware-spec-research.md), 호스트 OS 후보 비교 논쟁은 [2026-09-08 OS 플랫폼 조사](2026-09-08-os-platform-sources.md)가 담당한다. 이 문서는 vendor(pinklab) 쪽 실제 스택만 다루고, 호스트 OS 논쟁은 요약만 한다.

---

## 0. 요약

핑키프로의 공식 소프트웨어 스택은 **"제작사 전용 SD 이미지 + Ubuntu 24.04 계열 호스트 + ROS 2 Jazzy + colcon 워크스페이스"** 구조다. 공개 ROS 저장소([pinklab-art/pinky_pro](https://github.com/pinklab-art/pinky_pro))는 PC와 로봇 양쪽에서 git clone → rosdep → colcon build로 쓰는 것이 표준 흐름이고, 모터·LiDAR·IMU·ADC 드라이버가 전부 저장소 안에 자작 포함되어 있다. Nav2+slam_toolbox를 그대로 쓰며, 최종 `cmd_vel`은 Nav2 velocity_smoother와 teleop이 직접 발행한다 — **vendor 쪽에는 "최종 명령 단일 발행자 게이트" 개념이 없다.** 운용은 로봇 AP(`pinky_XXXX`)+Jupyter(:8888)+SSH(`pinky@192.168.4.1`)로 사람이 수동 launch하는 교육용 모델이고, systemd 자동 실행·자동 업데이트는 저장소 어디에도 없다.

---

## 1. 저장소·조직 식별 (FACT)

- 공식 ROS 저장소는 **`pinklab-art/pinky_pro`**다. 조사 지시에 있던 `pinklab-kr/pinky_pro`는 존재하지 않는다(404 확인 — GET https://github.com/pinklab-kr/pinky_pro → 404).
- README가 안내하는 clone 대상도 `https://github.com/pinklab-art/pinky_pro.git`이다. `reference/src/pinky_pro-main.zip 내 README.md` 49행
- `pinklab-art/pinky_study`는 ROS 코드가 없는 **교육 자료 저장소**이며, 제품 문서(wiki)를 호스팅한다. pinky_pro README가 "Pinky Pro 소개/초기 설정/수업 자료" 링크를 전부 이 wiki로 돌린다. `reference/src/pinky_pro-main.zip 내 README.md` 10–21행
- 과거 문서에 있던 `pinky_studio` 데스크톱 앱은 **`pinky_desktop`으로 이동했다.** live README는 release 링크를 `pinklab-art/pinky_desktop`으로 바꿨고(2026-09-21 커밋 `248e55a` "docs: update desktop app links"), frozen README는 아직 `pinky_studio`를 가리킨다. frozen/live README diff, [pinklab-art/pinky_desktop](https://github.com/pinklab-art/pinky_desktop)
- org 전체는 22개 공개 저장소로 `pinky_pro`, `pinky_desktop`, `pinky_study`, `pinky_lcd`, `pinky_zero_library`, `omx_follower_python` 등이 있다. [org 리포지토리 목록](https://github.com/orgs/pinklab-art/repositories). **`pinkylib`(로봇 저수준 Python 라이브러리)는 공개 저장소가 없다** — 아래 UNKNOWN 참고.
- 라이선스는 Apache-2.0. [LICENSE](https://github.com/pinklab-art/pinky_pro/blob/main/LICENSE), zip 내 `LICENSE`
- pinky_pro README의 Special Thanks가 밝히듯 ROS 2 패키지 모델 개발은 외부 협력자(byeongkyu)가 했고, 원본은 [byeongkyu/pinky_robot](https://github.com/byeongkyu/pinky_robot)이다. `reference/src/pinky_pro-main.zip 내 README.md` 29–32행

## 2. frozen zip vs live GitHub 차이

frozen zip은 live main과 **파일 단위 diff에서 하드웨어 스택 부분이 전부 동일**하다. 차이는 시뮬레이터 추가뿐이다.

| 항목 | frozen zip | live main (2026-09-21) |
|---|---|---|
| 패키지 10개 (bringup, description, emotion, gz_sim, imu_bno055, interfaces, lamp_control, led, navigation, sensor_adc) | 있음 | 동일 (해시 일치) |
| `pinky_mujoco` | **없음** | **추가** (2026-09-21 PR #6 병합) |
| `pinky_bringup/launch/bringup_sim.launch.xml` | 없음 | 추가 — `sim:=mujoco(기본)/gz` 선택 |
| `pinky_bringup/package.xml` | `pinky_mujoco` exec_depend 없음 | 추가 |
| `doc/arm64_guide.md` | 1~3단계만 | 2-1단계( `pinky_mujoco/setup.py`의 aarch64 skip 제거) 추가 |
| README 시뮬레이션 절 | Gazebo만 (`pinky_gz_sim launch_sim`) | MuJoCo가 기본, Gazebo는 `sim:=gz`. MuJoCo 의존성 `pip install --break-system-packages "mujoco==3.6.0" "trimesh>=4,<5" "pycollada>=0.9,<1"` |
| README 데스크톱 앱 링크 | `pinky_studio/releases/latest` | `pinky_desktop/releases` |
| `.gitignore` | `__pycache__/` 없음 | 추가 |

근거: frozen/live 트리 전체 파일 비교(2026-09-21 수행)와 [커밋 이력](https://github.com/pinklab-art/pinky_pro/commits/main/) — 최신 커밋 2026-09-21 `014a09f`(build(pinky_mujoco): skip install on aarch64). frozen zip에는 2026-06-04 커밋 `d576618`(web nav status/stop/initialpose)이 반영된 `nav2_web_server.py`의 `/api/nav/status`·`/api/nav/stop`·`/api/initialpose` 경로가 있으므로 **frozen 스냅샷은 2026-06-04 ~ 2026-09-20 사이**로 좁혀진다. `reference/src/pinky_pro-main.zip 내 pinky_navigation/scripts/nav2_web_server.py` 429–511행

결론: **우리가 파생한 소스(base)와 현재 vendor main의 구조·드라이버는 동일하다.** 이후 vendor 변화를 따지는 것은 시뮬레이터 트랙(MuJoCo)과 데스크톱 앱 이름뿐이다.

## 3. 호스트 OS·부팅

### 3.1 배포·플래시 (FACT)

- 핑키프로는 **제작사가 만든 전용 SD 카드 이미지**를 Google Drive에서 배포하고, `rpi-imager`로 굽는다. rpi-imager에서 CHOOSE DEVICE = Raspberry Pi 5, CHOOSE OS = "Use custom"(다운로드한 핑키 전용 이미지). [wiki 0. 초기설정 §1 SD 카드 세팅](https://github.com/pinklab-art/pinky_study/wiki/0.-%EC%B4%88%EA%B8%B0%EC%84%A4%EC%A0%95(PinkyPro)#1-sd-%EC%B9%B4%EB%93%9C-%EC%84%B8%ED%8C%85)
- 이미지에 **네트워크 등 초기 설정이 이미 들어 있다** — rpi-imager의 OS customization(사용자·Wi-Fi 사전 설정)을 하지 않는다. 위와 같음 (wiki: "핑키 이미지에 이미 있으므로 패스!").
- 이미지는 **버전이 매겨진다.** Pinky Studio(Desktop) 앱의 BLE 기능은 `pinky_pro_v1.8` 이상, 카메라 스트리밍은 `pinky_pro_v1.9` 이상 이미지가 요구된다. [pinky_desktop README](https://github.com/pinklab-art/pinky_desktop#readme), [MANUAL.md](https://raw.githubusercontent.com/pinklab-art/pinky_desktop/main/MANUAL.md)
- 라이다 유무로 두 가지 하드웨어 버전이 있고 SD 이미지로 구분한다. [wiki 0. 초기설정 §2 Version Configuration](https://github.com/pinklab-art/pinky_study/wiki/0.-%EC%B4%88%EA%B8%B0%EC%84%A4%EC%A0%95(PinkyPro))

### 3.2 부팅 흐름 (FACT)

1. 전원 인가 → 부팅 완료 시 **부저가 울리고** LCD에 Wi-Fi SSID(`pinky_XXXX`, 4자리 영숫자)와 비밀번호(`pinkypro`)가 표시된다. [wiki 0. 초기설정 §1 "전원 켜기"], [wiki 2.4 §1 "로봇과 wifi 연결"](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%A1%9C%EB%B4%87%ED%99%9C%EC%9A%A9))
2. 로봇은 **자체 Wi-Fi AP 모드**로 떠 있고 PC가 `pinky_XXXX`에 연결한다. 로봇 측 기본 주소는 `192.168.4.1`이다 (AP 미설정 시 Jupyter 접속 주소 `192.168.4.1:8888`, 웹 내비 서버 기본 `192.168.4.1:8080`). [MANUAL.md §6 Jupyter 접속], `reference/src/pinky_pro-main.zip 내 README.md` 210–212행
3. 외부 공유기 연결은 로봇에서 `wifi_setup.sh`(로봇 홈에 준비됨)를 실행해 설정하고, 성공하면 netplan 설정 파일(`/etc/netplan/90*`)이 생성된다. README 트러블슈팅은 이 파일을 `sudo rm /etc/netplan/90*`로 지우면 AP 직접 연결 모드로 돌아간다고 안내한다. [wiki 2.4 §1 "wifi_setup.sh"], `reference/src/pinky_pro-main.zip 내 README.md` 220–234행

### 3.3 호스트 OS 정체 (FACT + 간접 근거, 배포판명 공식 명시는 UNKNOWN)

공개 자료 어디에도 로봇 이미지의 배포판 이름이 직접 적혀 있지 않다. 다만 다음 FACT들이 겹치면 **Ubuntu 24.04 계열(Noble)**이라는 판단이 가장 강하다:

- README와 wiki가 **PC 표준 환경으로 Ubuntu 24.04 + ROS 2 Jazzy**를 명시하고, 로봇과 PC가 같은 ROS 스택을 공유한다. `reference/src/pinky_pro-main.zip 내 README.md` 34–40행, [wiki 2.4 §1](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%B4%87%ED%99%9C%EC%9A%A9))
- **netplan**: 외부 Wi-Fi 설정이 `/etc/netplan/90*` 파일을 만들고, 이를 지우는 트러블슈팅이 공식 문서다. netplan은 Ubuntu 계열의 표준 네트워크 설정 계층이다. `reference/src/pinky_pro-main.zip 내 README.md` 220–234행
- **PEP 668 / 전역 pip**: wiki가 `pip3 install jupyter --break-system-packages`를 안내하며 PEP 668(시스템 Python 보호)을 언급한다 — Ubuntu 24.04의 Python 3.12 체계와 일치한다. [wiki 2.4 §4](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%B4%87%ED%99%9C%EC%9A%A9))
- ROS 2 Jazzy는 Ubuntu Noble 24.04 **arm64를 Tier 1**으로 지정한다(amd64·arm64 모두). [REP-2000](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-2000.rst) "Jazzy Jalisco" 표
- lamp_control README의 systemd 예시가 `Requires=ufw.service / After=ufw.service`를 쓴다 — Ubuntu 기본 방화벽 체계이다. `reference/src/pinky_pro-main.zip 내 pinky_lamp_control/README.md` 36–37행

배포판·버전 문자열, 32/64bit 표기, 이미지 빌드 파이프라인은 공개 소스에 없으므로 UNKNOWN으로 남긴다(§11).

### 3.4 주변장치·부트 설정의 흔적 (FACT)

저장소에 `config.txt`·udev 규칙·부트 스크립트는 없지만, 코드가 요구하는 하드웨어 설정은 다음처럼 확정된다:

| 장치 | 요구되는 설정 | 출처 |
|---|---|---|
| RPLIDAR C1 | 시리얼 `/dev/ttyAMA0` (Pi 5 RP1 UART0) | `reference/src/pinky_pro-main.zip 내 pinky_bringup/launch/bringup_robot.launch.xml` 12–18행 |
| DYNAMIXEL XL330 ×2 | 시리얼 `/dev/ttyAMA4`, 1,000,000 baud (Pi 5 RP1 UART4) | `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/bringup.py` 23–24행 |
| BNO055 IMU | I2C `/dev/i2c-0`, 주소 0x28 | `reference/src/pinky_pro-main.zip 내 pinky_imu_bno055/src/main_node.cpp` 15, 25행 |
| ADC 마이컨트롤러 | I2C `/dev/i2c-1`, 주소 0x08 | `reference/src/pinky_pro-main.zip 내 pinky_sensor_adc/src/main_node.cpp` 16, 21행 |
| ST7789 LCD | SPI bus 0, CE0, 최대 80MHz, GPIO RST=27/DC=25/BL=18(BCM) | `reference/src/pinky_pro-main.zip 내 pinky_emotion/pinky_emotion/pinky_lcd.py` 7–9, 30–33행 |
| WS2812B LED ×8 | GPIO19 PWM, DMA 10, **Pi 5 전용 커널 모듈 `rp1_ws281x_pwm` insmod + dtoverlay + `pinctrl set 19 a3 pn`** | `reference/src/pinky_pro-main.zip 내 pinky_lamp_control/src/main_node.cpp` 12–27행, `pinky_lamp_control/README.md` 3–21행 |

WS2812는 Pi 5에서 기존 rpi_ws281x PWM 방식이 안 되므로 제작사가 커널 모듈 로드 스크립트 + systemd 유닛(`lamp_bringup.service`, User=root, WantedBy=multi-user.target)까지 예시로 제공한다. [rpi_ws281x Pi 5 지원 문서](https://github.com/jgarff/rpi_ws281x/wiki/Raspberry-Pi-5-Support), `reference/src/pinky_pro-main.zip 내 pinky_lamp_control/README.md` 11–49행. 실제 출하 이미지에 이 유닛이 들어가 있는지는 UNKNOWN이다(§11).

계정: SSH 사용자 `pinky`, 비밀번호 `1` (wiki). lamp README의 예시 경로는 `/home/robot/pinky_devices/`라는 다른 사용자명을 쓴다 — 예시 문서가 구버전 이미지 기준일 가능성이 있고, 출하 이미지의 실제 사용자 레이아웃은 UNKNOWN이다. [wiki 2.4 §1 ssh 접속], `reference/src/pinky_pro-main.zip 내 pinky_lamp_control/README.md` 14, 43행

## 4. ROS 2 설치·빌드 방식

- **설치 스크립트·Dockerfile·requirements 파일이 저장소에 없다.** 전체 파일 목록상 설치 자동화는 `rosdep install --from-paths src --ignore-src -r -y` 한 줄이 전부다. `reference/src/pinky_pro-main.zip 내 README.md` 51–60행, zip 전수 파일 목록(2026-09-21 확인)
- PC·로봇 공통 표준 흐름: `mkdir -p ~/pinky_pro/src` → clone → **rosdep** → **colcon build**. 로봇 위에서도 같은 흐름으로 빌드한다. [wiki 2.4 §1 ROS2 활용 환경설정](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%B4%87%ED%99%9C%EC%9A%A9)) — 이 위키 페이지의 빌드 스크린샷은 PC 기준이지만 사용 명령은 README와 동일하다
- **핵심 코드 비중은 Python이고, 저수준 센서 드라이버 3종만 C++이다:**
  - ament_python: `pinky_bringup`(모터+오도메트리+배터리 게이트), `pinky_led`, `pinky_emotion` — 각 `setup.py`/`package.xml`
  - ament_cmake: `pinky_imu_bno055`, `pinky_sensor_adc`, `pinky_lamp_control`, `pinky_interfaces`, `pinky_description`, `pinky_navigation`(ament_cmake_python 병행), `pinky_gz_sim`
- **rosdep 선언 밖의 의존성이 여럿이다** — 이들은 rosdep으로 설치되지 않으므로 전용 이미지에 사전 설치됐다는 뜻이다:
  - `dynamixel_sdk`(Python): `bringup.py`가 import하지만 `pinky_bringup/package.xml`에 선언 없음. `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/dynamixel_driver.py` 2행, `pinky_bringup/package.xml` 10–16행
  - `pinkylib`(Python, Battery/LED/Buzzer/Motor/Camera/IMU/IR/Ultrasonic): `battery_publisher.py`, `led_server.py`가 import, 공개 소스 없음. `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/battery_publisher.py` 4행, `pinky_led/pinky_led/led_server.py` 4행
  - `wiringPi`(C, I2C): IMU·ADC 노드가 `wiringPiI2C.h`를 쓰지만 package.xml에 선언 없음. `pinky_imu_bno055/src/main_node.cpp` 6행, `pinky_sensor_adc/src/main_node.cpp` 7행
  - `ws2811`(rpi_ws281x C 라이브러리): lamp_control이 링크하지만 package.xml 미선언. `pinky_lamp_control/CMakeLists.txt` 25–26행
  - `spidev`, `RPi.GPIO`, `PIL`(Pillow), `numpy`(LCD), `flask`(웹 서버): emotion·navigation이 사용, 미선언. `pinky_emotion/pinky_emotion/pinky_lcd.py` 1–5행, `pinky_navigation/scripts/nav2_web_server.py` 7행
- RPLIDAR C1 드라이버는 저장소에 없는 **외부 패키지 `sllidar_ros2`**를 launch에서 포함한다 (`sllidar_c1_launch.py`). `reference/src/pinky_pro-main.zip 내 pinky_bringup/launch/bringup_robot.launch.xml` 12행

## 5. 워크스페이스 구조

### 5.1 패키지 목록 (FACT)

| 패키지 | 빌드 타입 | 역할 | 주요 파일 |
|---|---|---|---|
| `pinky_bringup` | ament_python | 실기 코어: XL330 구동+오도메트리+배터리 경고 | `pinky_bringup/bringup.py`, `dynamixel_driver.py`, `battery_publisher.py`, `launch/bringup_robot.launch.xml`, `config/pinky_params.yaml` |
| `pinky_description` | ament_cmake | URDF/xacro·메쉬·RViz, robot_state_publisher | `urdf/robot.urdf.xacro`, `launch/upload_robot.launch.py` |
| `pinky_navigation` | ament_cmake(+py) | SLAM/Nav2 런치·파라미터·웹 브리지 | `launch/*.launch.xml` 14종, `params/mapper_params.yaml`, `params/nav2_params.yaml`, `scripts/nav2_web_server.py`+`index.html`, `map/*.pgm/yaml` |
| `pinky_interfaces` | ament_cmake | srv 4종: `SetLed`, `SetBrightness`, `SetLamp`, `Emotion` | `srv/*.srv` |
| `pinky_imu_bno055` | ament_cmake | BNO055 C++ 드라이버 (wiringPi) | `src/main_node.cpp` |
| `pinky_sensor_adc` | ament_cmake | ADC 마이컨트롤러 C++ 드라이버(초음파·IR·배터리) | `src/main_node.cpp` |
| `pinky_lamp_control` | ament_cmake | WS2812B 램프 C++ 서비스 (ws2811) | `src/main_node.cpp`, `README.md` |
| `pinky_led` | ament_python | LED 서비스 (pinkylib LED) | `pinky_led/led_server.py` |
| `pinky_emotion` | ament_python | ST7789 LCD 표정 서비스 | `pinky_emotion/pinky_lcd.py`, `emotion_server.py` |
| `pinky_gz_sim` | ament_cmake | Gazebo 시뮬레이션 (aarch64 빌드 skip) | `launch_sim.launch.xml`, `params/pinky_bridge.yaml`, worlds |
| (live만) `pinky_mujoco` | ament_python | MuJoCo 시뮬레이터(Gazebo 대체, aarch64 skip) | `bridge.py`, `model.py`, `world.py` |

### 5.2 실행 모드 = launch 파일 (FACT)

실기 관련 모드만 (시뮬레이션은 `gz_*/bringup_sim` 접두사로 대응):

| 모드 | launch | 내용 |
|---|---|---|
| 코어 브링업 | `pinky_bringup bringup_robot.launch.xml` | robot_state_publisher + joint_state_publisher(source_list=joint_states, 20Hz) + sllidar C1 + bringup 노드(파라미터: wheel_radius 0.027, wheel_separation 0.0961) + battery_publisher |
| SLAM 매핑 | `pinky_navigation map_building.launch.xml` | slam_toolbox `online_sync_launch.py` + `mapper_params.yaml`(mode: mapping) |
| 내비게이션 | `pinky_navigation bringup_launch.xml map:=<yaml>` | component_container_isolated 하나에 localization(map_server+amcl) + Nav 7노드, lifecycle_manager |
| 웹 SLAM | `pinky_navigation web_slam.launch.xml` | nav2_web_server(Flask, 0.0.0.0:8080) + navigation(velocity_smoother만) + slam_toolbox |
| 웹 Nav2 | `pinky_navigation web_nav2.launch.xml` | nav2_web_server + bringup_launch(map 인자) |
| PC 관제(RViz) | `map_view.launch.xml`, `nav2_view.launch.xml` | [ONLY PC] 표기, robot 측 X 없음 |
| LCD/LED 서비스 | `ros2 run pinky_emotion emotion_server`, `ros2 run pinky_led led_server` | README 실행 예시, launch에 미포함(수동 실행) |

근거: 각 launch 파일 원문 — `reference/src/pinky_pro-main.zip 내 pinky_bringup/launch/bringup_robot.launch.xml`, `pinky_navigation/launch/{map_building,bringup_launch,localization_launch,navigation_launch,web_slam,web_nav2}.launch.xml`, `pinky_description/launch/upload_robot.launch.py`, `README.md` 62–136행

### 5.3 노드 그래프 — 토픽/서비스 (FACT)

```
[telos / 실기]
teleop_twist_keyboard ─────────────┐
Nav2 velocity_smoother (cmd_vel_nav→cmd_vel) ─┤→ /cmd_vel → pinky_bringup(30Hz 루프)
                                                │     ├─→ /odom, /tf(odom→base_footprint), /joint_states
sllidar_ros2 ─→ /scan                           │     └─(구독) /battery/voltage
pinky_imu_bno055 ─→ /imu_raw                    │
pinky_sensor_adc ─→ /us_sensor/range            │
                   ─→ /ir_sensor/range          │
                   ─→ /batt_state               │
battery_publisher ─→ /battery/voltage, /battery/percent (5s)
nav2_web_server(Flask) ←구독 map/plan/costmap/TF, → NavigateToPose 액션, /initialpose, slam_toolbox SaveMap·Reset

[서비스] /set_led, /set_brightness (pinky_led), /set_lamp (pinky_lamp_control), /set_emotion (pinky_emotion)

[시뮬레이션(gz)] gz_bridge: /clock /tf /scan /camera/camera_info /joint_states /odom GZ→ROS, /cmd_vel ROS→GZ
```

근거: `bringup.py` 17–21, 84–95행, `pinky_imu_bno055/src/main_node.cpp` 21행, `pinky_sensor_adc/src/main_node.cpp` 27–29행, `battery_publisher.py` 12–22행, `nav2_web_server.py` 66–120행·429–511행, `navigation_launch.xml` 29, 85–86행(cmd_vel_nav→cmd_vel 리맵), `pinky_bridge.yaml` 전체

TF 트리: `map → odom → base_footprint → base_link → 바퀴/센서 링크`(URDF: rplidar_link, imu_link, front_camera_link 등). amcl이 map→odom, bringup이 odom→base_footprint. `pinky_description/urdf/pinky.urdf.xacro` 171–294행, `nav2_params.yaml` amcl 절

## 6. 하드웨어 드라이버 스택

### 6.1 구동 — XL330-M288-T (FACT)

- **Dynamixel SDK(Python) 직접 사용**, 프로토콜 2.0, `/dev/ttyAMA4`, 1Mbps, ID [1, 2] = 좌/우 바퀴. `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/bringup.py` 23–25행, `dynamixel_driver.py` 18–19행
- 컨트롤 테이블: Operating Mode(11)=1(속도 모드), Torque Enable(64), LED Red(65), Goal Velocity(104), Profile Acceleration(108)=200, Present Velocity(128), Present Position(132). 초기화는 **모터마다 reboot** 후 모드 설정·토크온·LED 온. `dynamixel_driver.py` 6–12, 45–57행
- 명령은 **GroupSyncWrite**(104, 4B), 피드백은 **GroupBulkRead**(128+132 연속 8B)로 폴링. RPM↔raw 변환 계수 1/0.229. `dynamixel_driver.py` 28–29, 59–98행
- 우측 바퀴는 부호 반전(`rpm_r = -...`), 인코더 적분으로 오도메트리 계산(PULSE_PER_ROT=4096, odom→base_footprint TF). `bringup.py` 108–153행
- **하드웨어 시리얼(UART4) + Dynamixel TTL 버스** 조합이다. U2D2 같은 USB 어댑터를 쓰지 않는다. 장치 경로가 코드에 하드코딩되어 있고 파라미터화되어 있지 않다(`SERIAL_PORT_NAME` 상수). `bringup.py` 23행

### 6.2 라이다 — RPLIDAR C1 (FACT)

- **외부 패키지 sllidar_ros2** 사용(자작 아님). `/dev/ttyAMA0`, frame `rplidar_link`, `scan_mode DenseBoost`, angle_compensate on. `reference/src/pinky_pro-main.zip 내 pinky_bringup/launch/bringup_robot.launch.xml` 12–18행

### 6.3 IMU — BNO055 (FACT)

- **자작 C++ 노드.** wiringPi I2C(`/dev/i2c-0`, 0x28), SYS_TRIGGER 리셋 후 Normal 모드, Operation Mode 0x08(IMU 모드), **100 Hz** 타이머로 레지스터 0x08부터 32B를 한 번에 읽어 acc/gyro/quaternion을 `sensor_msgs/Imu` `/imu_raw`로 발행(RealtimePublisher, 공분산 0.01 대각). `reference/src/pinky_pro-main.zip 내 pinky_imu_bno055/src/main_node.cpp` 14–61, 68–117행

### 6.4 초음파·IR·배터리 — ADC 마이컨트롤러 (FACT)

- **자작 C++ 노드(`pinky_sensor_adc`).** 보드 위 별도 MCU가 I2C slave(주소 0x08, `/dev/i2c-1`)로 5채널 ADC를 제공하고, ROS 노드가 20 Hz로 레지스터 5개를 폴링한다. `reference/src/pinky_pro-main.zip 내 pinky_sensor_adc/src/main_node.cpp` 16–53행
- 출력: `us_sensor/range`(sensor_msgs/Range, ULTRASOUND, FOV 0.26, min 0.02 / max 3.0 m, frame `ultrasonic_link` — US-016), `ir_sensor/range`(UInt16MultiArray 3채널 raw — TCRT5000×3), `batt_state`(sensor_msgs/BatteryState, 전압 = ADC/4096 × 4.096V ÷ (13/28) 분압, Li-ion, design_capacity 5.0). 같은 파일 56–91행
- 별도로 `battery_publisher`(Python, pinkylib Battery)가 5 s 주기로 `/battery/voltage`, `/battery/percent`를 발행한다 — **배터리 경로가 2개 병존**한다. `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/battery_publisher.py` 12–26행

### 6.5 LCD·LED (FACT)

- LCD(ST7789 2.4", 240×320): **자작 Python 드라이버** — spidev(0,0), 80MHz, RGB565, RST/DC/BL GPIO(27/25/18), 백라이트 PWM 1kHz. `reference/src/pinky_pro-main.zip 내 pinky_emotion/pinky_emotion/pinky_lcd.py`
- LED: 두 경로. (a) `pinky_led` Python 서비스(pinkylib LED, `set_led`/`set_brightness` 서비스) (b) `pinky_lamp_control` C++ 노드(ws2811 라이브러리, GPIO19/DMA10/8개/GBR, `set_lamp` 서비스 — mode 0 off/1 on/2 blink/3 dimming, 100Hz 애니메이션). `pinky_led/pinky_led/led_server.py`, `pinky_lamp_control/src/main_node.cpp` 12–67행
- 참고: org에는 공개 Python LCD 라이브러리 저장소 `pinky_lcd`가 별도로 존재한다. [pinklab-art/pinky_lcd](https://github.com/pinklab-art/pinky_lcd) — zip 내 `pinky_lcd.py`와의 관계(동일 코드 여부)는 대조하지 않았다.

### 6.6 카메라 — OV5647 (FACT: ROS 드라이버 부재 / UNKNOWN: 내부 파이프라인)

- **ROS 저장소에는 실기 카메라 드라이버 노드가 없다.** URDF에 `front_camera_link`만 있고 bringup launch에 카메라 노드가 없다. 카메라 토픽은 Gazebo 시뮬레이션에만 존재한다(`/camera/image_raw`, ros_gz_image image_bridge). `reference/src/pinky_pro-main.zip 내 pinky_description/urdf/pinky.urdf.xacro` 204–233행, `pinky_gz_sim/launch/launch_sim.launch.xml` 34–35행
- 실기 카메라는 **ROS 밖**에서 쓴다: wiki 센서 테스트가 `pinkylib.Camera`(Jupyter, start/play_jupyter/close), Pinky Studio가 카메라 스트리밍 탭(v1.9+ 이미지, 해상도 160×120~1280×960, FPS 1~30, "카메라는 한 곳에서만 사용할 수 있다" — 단일 소비자 제약 표현). [wiki 0. 초기설정 §3 6. 카메라], [MANUAL.md §7 카메라 스트리밍](https://raw.githubusercontent.com/pinklab-art/pinky_desktop/main/MANUAL.md)
- Picamera2/libcamera 사용 여부는 공개 소스에서 확증 불가(pinkylib 비공개) — UNKNOWN.

## 7. 런타임 아키텍처

### 7.1 제어 루프 (FACT)

- **단일 Python 노드(`pinky_bringup`)가 cmd_vel 구독 → 역기구학 → SyncWrite, 30 Hz 타이머로 피드백 폴링·오도메트리 적분·TF/joint_states 발행**을 한 프로세스에서 한다. rclpy 단일 스레드 spin. `reference/src/pinky_pro-main.zip 내 pinky_bringup/pinky_bringup/bringup.py` 86–101, 127–161행
- 속도 게이트는 두 층이다:
  1. 드라이버 내부 클램프: `MAX_RPM = 100`, 좌우 중 큰 값이 넘으면 비율 스케일. `bringup.py` 117–122행
  2. Nav2 velocity_smoother: max/min velocity `[0.25, 0.0, 1.5]` / `[-0.25, 0.0, -1.5]`, accel `[2.5, 0, 3.2]`, `velocity_timeout: 1.0`. `reference/src/pinky_pro-main.zip 내 pinky_navigation/params/nav2_params.yaml` 325–338행

### 7.2 안전 메커니즘 — 그리고 없는 것 (FACT)

- 있는 것: (a) 위의 RPM/속도 클램프 2층, (b) 저전압 **경고** — `battery/voltage` ≤ 6.8V면 log warn(정지·감속 동작 없음). `bringup.py` 33–34, 197–205행, (c) Nav2 진행 정지 검사(SimpleProgressChecker, 10s/0.5m), 충돌 전방 검사(RPP use_collision_detection), 목표 도달 시 0속도 발행(publish_zero_velocity). `nav2_params.yaml` 117–138, 164–171행
- **없는 것(코드상 확인):** cmd_vel 타임아웃 watchdog, deadman/estop 토픽, cliff/초음파에 의한 자동 정지, IMU 안전 로직. `pinky_bringup`은 IR·초음파·IMU 토픽을 **구독하지 않는다** — 안전 센서는 발행만 되고 제어에 묶이지 않는다. `bringup.py` 전체(구독은 cmd_vel과 battery/voltage뿐, 86–95행)
- **멀티 발행자 충돌 허용:** teleop과 Nav2(velocity_smoother)가 같은 `/cmd_vel`에 동시에 발행될 수 있고, 마지막 수신이 이긴다. 최종 발행자를 하나로 좁는 게이트가 없다. `bringup_robot.launch.xml` 20–24행 + `navigation_launch.xml` 86행
- 시리얼 실패 시: set_double_rpm 실패는 warn만 하고 계속, 종료 시 torque off + 0 RPM은 수행. `bringup.py` 124–125, 216–219행

### 7.3 SLAM / Nav2 구성 (FACT)

- SLAM: slam_toolbox `online_sync`(mapper_params: resolution 0.05, max_laser_range 10.0, loop closure on). `reference/src/pinky_pro-main.zip 내 pinky_navigation/params/mapper_params.yaml`, `launch/map_building.launch.xml`
- Localization: nav2_map_server + AMCL(DifferentialMotionModel, initial_pose [0,0,0] 고정). `localization_launch.xml`, `nav2_params.yaml` 1–41행
- Planner/Controller: NavfnPlanner + **RegulatedPurePursuitController 20 Hz**(desired_linear_vel 0.2 m/s, 제자리 회전 임계 0.35 rad/1.0 rad/s, 장애물 근접 감속 on) — 한국어 주석 파라미터. `nav2_params.yaml` 70–148행
- Costmap: footprint 12×12cm(`[[0.06,0.06],...]`, robot_radius 주석 처리), inflation_radius 0.15, local 3×3m rolling 5Hz / global 1Hz. `nav2_params.yaml` 173–250행
- Behavior/복구: spin, backup, drive_on_heading, wait, assisted_teleop. `nav2_params.yaml` 286–312행
- 목표 판정: xy 0.25 m, yaw 0.25 rad. `nav2_params.yaml` 155–159행
- 실기 Nav 조합은 composition(component_container_isolated) 1컨테이너에 lifecycle 7노드. `bringup_launch.xml` 11–32행

### 7.4 상태 모니터링 (FACT)

- 표준 토픽(/odom, /joint_states, /scan, /imu_raw, /battery/*, /batt_state)과 **진단 전용 서비스/토픽은 없다.** 상태 관측 수단은 웹 브리지(`/api/state`가 map/plan/pose/costmap 스냅샷)와 RViz가 전부다. `reference/src/pinky_pro-main.zip 내 pinky_navigation/scripts/nav2_web_server.py` 429–443행

## 8. 배포·업데이트·운용

- **출하 이미지**: 제작사가 만든 SD 이미지를 Google Drive로 배포, rpi-imager로 굽는다(§3.1). **이미지 빌드 파이프라인(스크립트/레시피)은 공개되어 있지 않다.** [wiki 0. 초기설정 §1]
- **ROS 스택 자동 실행 증거 없음**: 저장소에 ROS용 systemd 유닛·rc.local·autostart 설정이 없다(전수 검색: systemd/udev/autostart 키워드는 nav2 lifecycle `autostart` 인자와 lamp README 예시만 적중). wiki 사용 흐름도 모두 사람이 SSH/Jupyter에서 `ros2 launch`를 수동 실행한다. [wiki 2.4 전체](https://github.com/pinklab-art/pinky_study/wiki/2.4-Pinky-Pro(part4%E2%80%90%EC%8B%A4%EB%AC%BC%EB%B4%87%ED%99%9C%EC%9A%A9))
- 저장소 유일의 systemd 예시는 WS2812 커널 모듈 로더용(`lamp_bringup.service`, root, multi-user.target)이다 — ROS 앱이 아니라 하드웨어 초기화용이다. `reference/src/pinky_pro-main.zip 내 pinky_lamp_control/README.md` 31–49행
- **업데이트 메커니즘 없음**: OTA/A/B/패키지 업데이트 절차가 공개 자료에 없고, 이미지 교체(다시 굽기)와 `git pull + colcon build`가 유일한 갱신 경로다. 이미지 버전 요건이 "재구워서 올려야 한다"는 형태로만 기술된다. [pinky_desktop README 버전 요건](https://github.com/pinklab-art/pinky_desktop#readme)
- **로그 정책 없음**: RCUTILS_LOGGING_BUFFERED_STREAM 환경설정(launch 내)과 각 노드 콘솔 로그가 전부다. 로그 파일·상한·수집은 없다. `reference/src/pinky_pro-main.zip 내 pinky_navigation/launch/navigation_launch.xml` 3행
- 온보딩 도구: **Pinky Studio(Desktop)** — BLE로 `pinky_xxxx` 검색·연결 → Wi-Fi 설정, `ROS_DOMAIN_ID`(0–232) 적용(이후 `source ~/.bashrc`), Jupyter(:8888) 열기, 카메라 스트리밍(v1.9+). Tauri 2(Rust, btleplug) + Next.js 16/React 19. [MANUAL.md](https://raw.githubusercontent.com/pinklab-art/pinky_desktop/main/MANUAL.md), [pinky_desktop README 기술 스택](https://github.com/pinklab-art/pinky_desktop#readme)

## 9. 멀티로봇·네트워크

- **격리 수단은 ROS_DOMAIN_ID 하나다.** wiki 절차: 로봇 `~/.bashrc`에 `export ROS_DOMAIN_ID=<원하는 번호>`를 쓰고 PC도 같은 값으로 맞춘다. namespace는 쓰지 않는다(시뮬레이션 launch에만 namespace 인자 존재). [wiki 2.4 §1 .bashrc ROS_DOMAIN_ID], `reference/src/pinky_pro-main.zip 내 pinky_gz_sim/launch/launch_sim.launch.xml` 4행
- 도메인 설정은 수동(.bashrc) 또는 Pinky Studio BLE(0–232 범위 입력, 적용 후 source 필요). [MANUAL.md §5](https://raw.githubusercontent.com/pinklab-art/pinky_desktop/main/MANUAL.md)
- **RMW/DDS 튜닝 없음**: zip 전수 검색에서 RMW/FASTRTPS/ZENOH/CYCLONE/ROS_DOMAIN/ROS_LOCALHOST_ONLY 설정이 전무하다. 따라서 Jazzy 설치 기본 RMW(eProsima Fast DDS — REP-2000에서 `rmw_fastrtps_cpp*`가 기본 표기)에 전적으로 의존한다. [REP-2000](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-2000.rst) Jazzy Middleware 표
- **무선 대역 문제를 공식 인지**: 여러 대의 Pinky가 한 공유기를 공유하면 DDS 트래픽으로 통신이 끊긴다 → 공식 트러블슈팅은 "공유기 연결을 끊고 PC와 로봇이 AP로 직결"하는 운용을 권한다(netplan 90* 삭제). 다중 로봇을 같은 도메인·같은 무선망에 올리는 구성의 한계를 vendor 스스로 문서화한 것이다. `reference/src/pinky_pro-main.zip 내 README.md` 220–234행
- 원격 접속 3종: SSH(`pinky@192.168.4.1`, pw 1), Jupyter(`:8888`, AP 미설정 시 `192.168.4.1:8888`), 웹 Nav2(`:8080`, 실기 기본 `192.168.4.1:8080`). [wiki 2.4 §1], [MANUAL.md §6], `reference/src/pinky_pro-main.zip 내 README.md` 210–215행

## 10. Rosy OS 참조 포인트

비교 기준은 이 저장소 현재 구조: `src/{core,apps,hardware,navigation,sim,site}` 도메인 그룹, `core`(FastAPI+rclpy 단일 프로세스)가 유일한 외부 API·최종 `cmd_vel` 발행자(D-2), 하드웨어 프로필 YAML, signed image + Host Agent 배포.

### 10.1 참조할 만한 것 (판단 + 근거)

| upstream 요소 | Rosy OS 적용 포인트 |
|---|---|
| 한 노드에 모터+오도메트리+배터리 게이트를 묶은 `pinky_bringup` 단일 코어 구조 | `src/hardware/bringup` 슬라이스 설계와 같은 방향임을 vendor에서도 확인. 30Hz 루프, 오도메트리 적분, SyncWrite/BulkRead 조합은 벤치마크 비교 대상. `bringup.py` 전체 |
| 속도 클램프 2층(MAX_RPM 드라이버 클램프 + velocity_smoother) | SAF 계열 요구의 최소 구현 예. Rosy OS는 CORE 게이트가 담당하므로, upstream의 값(0.25 m/s, 1.5 rad/s, RPM 100)은 프로필 기본값 후보로 비교 가능. `nav2_params.yaml` 325–338행 |
| 하드웨어 매핑 FACT(UART0=LiDAR, UART4=모터, i2c-0=IMU, i2c-1=ADC MCU, SPI0=LCD, GPIO19=WS2812, 배터리 분압 13/28, wheel 0.027/0.0961) | `src/core/core/config/profile.pinky_pro.yaml`의 검증 데이터. 실물 commissioning(G0–G5)에서 readback할 기준값이 된다. §3.4·§6 각 출처 |
| slam_toolbox + AMCL + RPP 전체를 파라미터 YAML로만 커스터마이징(launch는 공식 nav2_bringup 런치 복제) | Nav2를 "래핑이 아니라 파라미터로" 다루는 방식. Rosy OS navigation 슬라이스도 같은 접근 유지 권장. `pinky_navigation/launch/navigation_launch.xml`은 nav2_bringup 표준 런치의 거의 복제다 |
| 웹 브리지의 작은 REST 표면(/api/state, /api/goal, /api/initialpose, /api/nav/status·stop, /api/slam/reset·save_map) | FastAPI core의 REST/WS 표면 설계에서 "최소 실용 세트" 사례. 단, upstream은 목적지를 액션(NavigateToPose)으로 통과시키고 cmd_vel을 웹에서 직접 쓰지 않는다 — CORE 계약과 양립. `nav2_web_server.py` 429–511행 |
| AP 모드 기본 + Jupyter/SSH + BLE 설정 앱의 온보딩 흐름, 도메인·Wi-Fi를 개별 장비에 배정하는 경험 | D-154(공통 이미지 + per-device personalization)와 같은 문제의 vendor 쪽 해법. BLE 프론트엔드 유무와 무관하게 "개인화는 출하 후 장비별 1회" 원칙만 참조 가능. [MANUAL.md] |
| 공유기 과부하 트러블슈팅(DDS 무선 대역) | 무선 다중 로봇 실험 시 대역 한계의 공식 근거. Rosy OS의 DDS 장비 간 격리 검증 항목과 직결. `README.md` 220–234행 |

### 10.2 이미 의도적으로 갈라선 것 (판단 + 근거)

| 항목 | upstream | Rosy OS | 판단 |
|---|---|---|---|
| 최종 cmd_vel 소유 | Nav2 velocity_smoother·teleop이 직접 발행, 중재자 없음 | CORE Command Manager가 유일 발행자(D-2) | 갈라섬 유지. upstream은 teleop과 Nav2 동시 발행 충돌을 그대로 허용한다(§7.2) |
| 안전 센서 결합 | IR/초음파/IMU는 발행만 되고 제어에 미결합, 저전압은 경고만 | SAF 계열(cliff 감속·배터리 무결성 D-27 등) | 갈라섬 유지. vendor 구조는 "센서가 있어도 안전에 쓰지 않는다"는 반례로 참조 |
| 배포 | 전용 SD 이미지(빌드 파이프라인 비공개) + 수동 launch | signed image + Host Agent + systemd | 갈라섬 유지. 이미지 내용물을 재현할 수 없다는 점이 결정적 차이다 |
| 다중 로봇 식별 | ROS_DOMAIN_ID만(사람이 .bashrc/BLE로 배정) | `ROS_DOMAIN_ID`=40+N, `ROSY_NAMESPACE` 파생, 부재 시 기동 정지(D-33/D-4) | 갈라섬 유지. 단, vendor가 도메인 배정을 "설정 앱 1회 작업"으로 강제하는 UX는 참조 가치가 있다 |
| 시뮬레이터 | Gazebo(→MuJoCo 병행, 2026-09-21) | Gazebo(ros_gz) + rosy 시뮬레이션 슬라이스 | MuJoCo 추가는 관찰만. 지금 갈아탈 근거는 없고, frozen 파생 소스와 무관한 vendor의 신설편 방향이다 |
| 외부 API | ROS 서비스(/set_led 등) + 작은 Flask 웹 | FastAPI core 단일 게이트웨이(외부 클라이언트는 ROS를 말하지 않음) | 갈라섬 유지. upstream의 LED/LCD/램프 서비스들은 CORE feature 뒤로 숨기는 대상이다 |
| 패키지 명명 | `pinky_*` 플랫 10패키지 | 도메인 그룹 `src/{core,apps,hardware,navigation,sim,site}`(D-147, D-16 rename) | 갈라섬 유지 |

## 11. FACT / UNKNOWN 총정리

### FACT (확증 — §별 출처 참조)

1. 공식 org·저장소는 `pinklab-art`이다(`pinky_pro`/`pinky_study`/`pinky_desktop` 등). `pinklab-kr`은 없다. (§1)
2. 공식 권장 개발 환경은 Ubuntu 24.04 + ROS 2 Jazzy(x86_64 권장, ARM64 별도 가이드)이고, 로봇 이미지는 제작사 전용 SD 이미지(rpi-imager로 굽기)이며 버전이 매겨진다(v1.8/v1.9 언급). (§3.1)
3. 부팅 시 부저 + LCD에 AP 정보 표시, AP `pinky_XXXX`/`pinkypro`, 로봇 기본 주소 192.168.4.1, SSH `pinky`/`1`, Jupyter 8888, 외부 Wi-Fi는 `wifi_setup.sh`(netplan 90* 생성). (§3.2)
4. 설치·빌드는 git clone → rosdep → colcon이 전부이고 설치 스크립트/Dockerfile/requirements는 없다. (§4)
5. 패키지 10개(핵심: bringup/navigate/sensor/driver/interfaces/sim), Python 3패키지 + C++ 4드라이버+interfaces+description+navigation+gz_sim. (§5.1)
6. XL330은 Dynamixel SDK(Python)·프로토콜 2.0·UART4(1Mbps)·ID 1/2·속도 모드·SyncWrite/BulkRead. RPLIDAR C1은 외부 sllidar_ros2·UART0·DenseBoost. BNO055는 자작 C++(wiringPi, i2c-0, 100Hz). ADC MCU는 자작 C++(i2c-1, 20Hz, 초음파/IR 3채널/배터리 13/28 분압). LCD는 자작 Python(spidev, ST7789). LED는 ws2811 C++ 서비스 + pinkylib Python 서비스 병행. (§6)
7. 실기 카메라 ROS 드라이버는 저장소에 없다(카메라는 ROS 밖 pinkylib·Pinky Studio 사용, 단일 소비자). (§6.6)
8. 제어 루프 30Hz, 클램프는 MAX_RPM 100 + velocity_smoother(0.25 m/s / 1.5 rad/s), 저전압 6.8V는 경고만, deadman/watchdog/cliff 연동 없음, cmd_vel 다중 발행자 허용. (§7)
9. SLAM=slam_toolbox(online_sync), Local=AMCL, Controller=RPP 20Hz 0.2m/s, planner=Navfn, footprint 12×12cm, 복구=spin/backup/wait/assisted_teleop. (§7.3)
10. 운용은 수동 launch가 표준이고 ROS용 systemd·자동 업데이트·로그 정책은 없다. systemd 예시는 WS2812 커널 모듈 로더 하나뿐. (§8)
11. 다중 로봇 격리는 ROS_DOMAIN_ID 수동 배정(.bashrc 또는 BLE 앱, 0–232)뿐이고, RMW/DDS 튜닝은 전무(Jazzy 기본 rmw_fastrtps 의존), 무선 공유기 병목을 공식 문서가 인지·회피 권고한다. (§9)
12. frozen zip과 live main의 차이는 시뮬레이터(MuJoCo 추가)와 문서·링크뿐이고 하드웨어 스택은 동일하다. (§2)

### UNKNOWN (소스에서 확인 불가 — 추측으로 기록 금지)

1. **출하 이미지의 배포판·버전 문자열**: Ubuntu 24.04 계열이라는 간접 근거(netplan, PEP 668, ufw, Jazzy Tier 1)는 강하지만 공식 문시가 없다. 이미지 내부에서 `cat /etc/os-release`로만 확정된다.
2. **이미지 빌드 파이프라인**: 베이스 이미지, 패키지 고정, 빌드 스크립트 — 전부 비공개. 재현 불가.
3. **pinkylib 내용**: 모터/카메라/IMU/배터리 저수준 구현(특히 Camera가 Picamera2/libcamera/V4L2 중 무엇을 쓰는지), 소스 비공개, 공개 저장소 없음.
4. **ROS 스택의 부팅 자동 실행 여부**: 출하 이미지에 bringup을 띄우는 유닛이 있는지 확인 불가(공개 자료의 사용 흐름은 전부 수동).
5. **udev 규칙·config.txt 부트 설정 내용**: UART/i2c/spi 활성화와 디바이스 노드 권한을 이미지가 어떻게 잡았는지 공개 자료 없음.
6. **핀 매핑**: ttyAMA0/ttyAMA4·i2c-0/i2c-1·SPI CE0의 물리 헤더 배선. 코드는 장치 경로만 확정.
7. **출하 이미지의 systemd 실체**: lamp README 예시(`lamp_bringup.service`, `/home/robot/...`)가 실제 이미지에 적용됐는지, `pinky` 사용자 체계와 어떤 관계인지.
8. **`pinky_test` 폴더·`wifi_setup.sh` 본체**: wiki가 로봇 이미지 안에 있다고 안내하지만 소스는 비공개.
9. **BLE 프로토콜**: Pinky Studio ↔ 로봇 BLE 통신 규격(서비스/특성 UUID) 비공개.
10. **다중 로봇 동시 운용의 공식 답**: 도메인 배정 외에 DDS 격리·QoS 튜닝·무선 채널 설계는 문서화되어 있지 않다(공유기 분리 권고가 유일).
11. **OMX 통합 스택**: `omx_follower_python` 등 org 저장소는 있으나 pinky_pro에 ROS 통합 패키지는 없다(2026-09-12 탑재 조사의 HOLD 사항 유지).

## 12. 수행하지 못한 것·방법 비고

- **위키 이미지 원본 판독**: 과거 기록(2026-09-12 문서)과 달리 이번에는 wiki 본문 텍스트 전체를 정상 수신해 이미지 의존 없이 절차를 확인했다. 단, wiki 스크린샷(빌드 화면·센서 출력 그래프 등)은 텍스트 주변 기술로만 판독했다.
- **ROS docs 사이트 직접 인용 실패**: docs.ros.org가 봇 차단(Anubis)되어 Jazzy 기본 RMW 근거는 [REP-2000 raw](https://raw.githubusercontent.com/ros-infrastructure/rep/master/rep-2000.rst)로 대체 확증했다.
- **pinkylib 소스 확보 실패**: org 목록·웹검색에서 공개 저장소를 찾지 못했다(§11 UNKNOWN 3).
- **실기·시뮬레이션 실행 검증 없음**: 이 문서의 모든 동작 서술은 소스 코드와 문서 해석이며, 부팅·주행 실측이 아니다. Pinky Pro G0–G5 실기 검증 게이트는 [2026-09-21-pinky-device-commissioning-design.md](2026-09-21-pinky-device-commissioning-design.md)가 다룬다.
- 분석용 해제본(`X:\DevTemp\opencode\pinky-pro-research\`)은 요청에 따라 삭제하지 않고 남겨 둔다.
- **UNKNOWN 폐쇄 경로(후속)**: 실물 vendor 이미지(카드 A)에서
  `deploy/robot/capture-vendor-baseline.sh`(읽기 전용 캡처)를 실행해 §11 대부분을
  닫는 절차가 [commissioning 설계 §7](2026-09-21-pinky-device-commissioning-design.md)에
  추가됐다.
