# Raspberry Pi 5 Motor Commissioning Design

## 목표

Rosy를 Raspberry Pi OS Lite 64-bit에 빠르게 반복 배포하고, 유선망 없이 Wi-Fi 인터넷과 같은 WLAN의 다른 단말 접속을 확인한 다음, UART 기반 DYNAMIXEL 모터를 안전하게 단계별 승인한다. 첫 설치와 업그레이드는 계속 `core` 모드로 시작하며 모터는 자동으로 움직이지 않는다.

## 운용 단계와 상태

배포 상태는 `core`, `motor`, `hardware` 세 단계로 분리한다. `core`는 FastAPI와 대시보드만 실행한다. `motor`는 `rosy-core`와 모터 노드만 실행하므로 LiDAR가 아직 연결되지 않아도 구동계 시험이 가능하다. `hardware`는 모터와 LiDAR를 함께 실행하는 최종 현장 모드다. 설치기는 언제나 `core`로 되돌려 시작하며, 작업자가 커미셔닝에 성공한 뒤에만 명시적으로 `motor` 또는 `hardware`로 승격한다.

## Wi-Fi 및 다른 단말 접속

Pi는 Raspberry Pi Imager에서 설정한 NetworkManager Wi-Fi station 연결을 사용한다. 장비 검증기는 `wlan0` 연결, IPv4, 기본 경로, DNS, 외부 HTTPS, 로컬 FastAPI와 대시보드를 각각 판정한다. Windows 수용 스크립트는 SSH가 가능한 배포 PC에서 Pi의 WLAN IPv4를 읽고 해당 주소와 mDNS 주소의 `/api/v1` 및 `/dashboard`에 직접 HTTP 요청한다. 이 검사는 Pi 내부의 localhost 확인과 달리 AP client isolation, 방화벽, 잘못된 바인딩을 발견한다.

## UART 및 무토크 사전검사

현재 모터 포트 `/dev/ttyAMA4`에 맞춰 Raspberry Pi 5의 `uart4-pi5` 오버레이를 사용한다. 커미셔닝 도구는 `/boot/firmware/config.txt`의 오버레이, serial console 충돌, 장치 노드, runtime 사용자의 dialout 권한을 검사한다. 이어서 motor 전원을 켠 상태에서 DYNAMIXEL Protocol 2.0, 1 Mbps, ID 1과 2에 ping을 수행한다. 이 사전검사는 torque enable이나 goal velocity 레지스터를 쓰지 않는다.

포트, baudrate와 ID는 환경변수와 ROS launch argument로 전달한다. Compose 컨테이너 내부 경로는 안정적으로 `/dev/rosy-motor`를 사용해 호스트 장치 이름과 분리한다. 값은 숫자·절대 장치 경로·허용 ID 목록으로 검증하고 shell command 문자열로 실행하지 않는다.

## 직접 제어와 안전 경계

FastAPI 대시보드는 `MANUAL` 모드에서만 활성화되는 방향 버튼을 제공한다. 작업자는 바퀴가 들려 있고 물리 전원 차단이 준비됐다는 체크박스를 매 접속마다 확인해야 한다. 버튼을 누르는 동안 100 ms 간격으로 기존 `/api/v1/teleop` 엔드포인트에 저속 명령을 보낸다. 기본값은 직진 0.05 m/s, 회전 0.35 rad/s이며 서버 설정의 기존 최대값 아래로 유지한다.

pointer release/cancel/leave, touch 취소, 브라우저 blur, 페이지 숨김, 연결 오류에는 즉시 zero 명령을 전송한다. zero 명령은 중복 가능하며 `sendBeacon`처럼 인증 헤더를 잃는 경로를 사용하지 않는다. UI는 편의 계층일 뿐이며 기존 core 500 ms watchdog과 driver 500 ms deadman이 최종 정지를 강제한다. Emergency stop은 계속 viewer 역할에서도 실행 가능하고 해제는 administrator만 가능하다.

## 검증과 실제 장비 경계

정적 테스트는 Compose 프로필 분리, UART 인자 전달, 무토크 ping, 설치 스크립트의 overlay 설정, 다른 단말 수용 검사, UI의 모든 정지 이벤트를 확인한다. Python, shell, PowerShell, JavaScript 문법 검사와 core 테스트, deadman 테스트, Compose 해석, Docker 빌드를 수행한다.

로컬 성공은 실제 모터 배선을 증명하지 않는다. Pi에서는 `core` 배포, WLAN 외부 단말 접속, UART preflight, DYNAMIXEL 무토크 ping, `motor` 모드 기동, 바퀴를 든 상태의 전진·후진·좌·우 hold-to-drive, 버튼 해제 정지, Wi-Fi 차단 정지, E-stop 순서로 기록한다. 각 단계가 실패하면 다음 단계로 진행하지 않는다.

