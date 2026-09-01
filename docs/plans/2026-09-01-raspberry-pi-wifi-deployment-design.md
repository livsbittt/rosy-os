# Raspberry Pi 5 Wi-Fi Deployment Design

## 목표와 배포 모델

Rosy의 첫 Raspberry Pi 5 배포는 별도 배포판을 만드는 대신 공식 Raspberry Pi OS Lite 64-bit를 기반으로 한다. 작업자는 Raspberry Pi Imager에서 hostname `rosy-01`, 대한민국 WLAN 규제 도메인, 관리 사용자, Wi-Fi SSID, SSH 공개키를 장비별로 설정한다. Wi-Fi 비밀번호와 개인 SSH 키는 저장소나 재사용 이미지에 넣지 않는다. 첫 부팅 후 Pi는 유선 연결 없이 WLAN에 접속하고, 같은 WLAN의 PC는 `ssh rosy@rosy-01.local` 및 `http://rosy-01.local:8080/dashboard`로 접근한다. mDNS가 차단된 환경에서는 검증 스크립트가 표시하는 `wlan0` IPv4 주소를 사용한다.

이 방식은 “이미지를 굽는다”는 운영 경험을 유지하면서도 장비별 비밀값이 포함된 golden image 복제를 피한다. 완전 커스텀 이미지는 수십 GB의 Linux 빌드 환경과 별도 artifact 서명·회수 절차가 필요한 `pi-gen` 제조 단계로 미룬다. 첫 현장 배포는 표준 OS 이미지와 버전 관리되는 Rosy 설치 계약을 결합한다.

## 네트워크와 접속 경계

Raspberry Pi 5의 내장 dual-band 802.11ac Wi-Fi를 WLAN station 모드로 사용한다. 연결된 SSID, `wlan0` 주소, 기본 route, DNS, 외부 HTTPS를 각각 검사한다. SSID 연결은 LAN 접속만 의미하며 인터넷을 보장하지 않는다. 인터넷은 공유기 또는 모바일 핫스팟이 default gateway, DNS, upstream access를 제공할 때 가능하다. 반대로 guest/client isolation이 활성화된 WLAN은 Pi가 인터넷에 접속해도 PC에서 SSH나 8080 포트에 접근하지 못할 수 있으므로 별도 실패 사유로 안내한다.

FastAPI는 기존 `0.0.0.0:8080`과 host network 구성을 유지한다. 별도 Node 서버나 프록시는 추가하지 않는다. 방화벽이 있다면 8080을 전체 인터넷이 아닌 신뢰 WLAN 대역에서만 허용해야 한다. 기본 설치는 기존 요구대로 `rosy-core`만 자동 기동하고, UART 장치와 물리 deadman 검증 후에만 `ROSY_RUNTIME_MODE=hardware`로 승격한다. 같은 라디오에서 AP와 upstream STA를 동시에 운영하는 복구 hotspot은 라우팅·NAT·보안 복잡도가 있으므로 이번 범위에서 제외한다.

## 설치, 비밀값과 실패 처리

Windows 배포 스크립트는 현재 Git `HEAD`만 archive하고 SHA-256을 생성해 SCP로 전송한다. dirty 파일이나 Wi-Fi 비밀번호는 포함하지 않는다. Pi 설치 스크립트는 모델·arm64·Raspberry Pi OS·인터넷을 사전 검사하고, Docker의 공식 Debian apt 저장소에서 Engine/Buildx/Compose를 설치한다. `/opt/rosy`, `/var/lib/rosy`, `/etc/rosy`를 최소 권한으로 준비하고, Rosy API 토큰은 Pi 안에서 무작위 생성해 root 소유의 초기 자격 파일에만 기록한다.

설치는 재실행 가능해야 하며 기존 `/etc/rosy/rosy.yaml`과 데이터는 덮어쓰지 않는다. Docker 이미지 빌드나 서비스 기동이 실패하면 systemd를 활성화하지 않고 정확한 복구 명령을 출력한다. 네트워크 검증은 WLAN/LAN 실패를 `FAIL`, 인터넷 부재를 설치 전에는 `FAIL`·설치 후에는 `WARN`, 대시보드 실패를 `FAIL`로 구분한다. 실제 Pi 5 부팅, WLAN 접속, 전원 재인가, 온도, UART와 모터는 코드 검증으로 대체하지 않고 물리 승인까지 `HOLD`로 남긴다.

## 검증 전략

정적 계약 테스트는 installer가 편의 설치 스크립트나 hard-coded secret를 사용하지 않는지, core-only 기본 모드인지, systemd가 network-online 및 Docker 뒤에 시작하는지, Wi-Fi 검증이 SSID·주소·route·DNS·HTTPS·dashboard를 분리하는지 검사한다. 모든 shell 파일은 LF와 `bash -n`을 통과해야 한다. PowerShell 전송 스크립트는 AST parser로 문법 검사하고 Git archive 및 SHA-256 계약을 확인한다.

기존 61개 Python 테스트와 Compose config를 다시 실행하고 core 이미지를 빌드한다. 로컬 검증은 스크립트·컨테이너 계약까지만 증명한다. 장비 승인에서는 Imager로 실제 SD를 기록하고, 유선 연결 없이 boot, `rosy-01.local` SSH, WLAN IP, 외부 HTTPS, 다른 Wi-Fi 장치의 dashboard 접속, 재부팅 후 자동 복구를 기록한다. 공유기의 client isolation 때문에 dashboard가 차단되면 Rosy 장애가 아니라 네트워크 `HOLD`로 분류한다.
