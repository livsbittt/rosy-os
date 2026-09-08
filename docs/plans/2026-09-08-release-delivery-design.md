# ROSY 릴리스 전달과 로컬 운용 검증

사용자 승인 범위: Pi는 컨셉 단계이고 공개 GitHub 저장소도 검토 중이다. 저장소 생성,
공개 게시, 실제 장비 적용은 수행하지 않는다. 현 checkout의 Fleet 작업과 격리한다.

## 선택

GitHub Releases의 서명 번들을 로봇이 pull한다. `git pull` 후 현장에서 빌드하는 방법은
실행물 식별과 복구를 어렵게 한다. 전체 SD/rootfs OTA는 부트 슬롯과 전원손실 복구가
필요하므로 초기 ROSY 런타임 번들 업데이트와 분리한다. 두 대안 대신 기존 Ed25519,
manifest, activation journal을 재사용한다.

## 흐름

1. 오프라인 서명 환경에서 runtime/ 및 images/를 manifest와 함께 tar.zst로 묶는다.
2. GitHub 게시 workflow는 이미 서명된 번들을 검증한 뒤 명시적 실행으로 게시한다.
   일반 CI에 개인키를 넣지 않는다. 공개 repo/token 없는 다운로드를 지원한다.
3. 호스트 timer는 설정된 owner/repo의 정식 릴리스만 확인한다. 설치는 하지 않는다.
4. stage는 경로 탈출, 링크, 중복, 특수 파일, 크기 초과를 거부하고 서명·checksum·
   기종·schema·manifest의 파일 목록까지 검사한다. 임시 트리만 변경한다.
5. install은 root CLI에서 정지/비상정지 및 core-only 조건을 확인하고 기존 Updater로
   활성화한다. Docker에서 실제 실행 이미지 ID와 container health를 검사한다.
6. 실패 시 이전 activation으로 돌아오며 모터를 자동으로 재개하지 않는다.

## 상태 소유권

서명·generation·activation은 기존 계약을 따른다. config/data generation은 설치 시점
불변 복구본이다. 실제 쓰기는 data-working/<generation> 사본에서 수행한다. 활성화
레코드의 generation 하나로 복구본과 작업본을 모두 도출한다. 이전 작업본도 유지하여
롤백에서 새 schema를 읽지 않는다. config schema 1/data schema 1만 지원하며 migration
코드를 번들에서 실행하지 않는다. 사용자 config/identity/key는 번들로 덮어쓰지 않는다.

## 검증과 한계

실제 Ed25519 키로 서명/변조, 위험 archive, 크기 제한, 실패 download, 버전 비교,
CLI 명령, install→failed health→rollback을 임시 root에서 시험한다. CI에 Fleet와
새 배포 시험을 포함한다. 대표 가드는 mutation red/green으로 검증한다.
실제 ARM64 Docker import, GPIO/UART, Pi boot, Wi-Fi, 주행은 HOLD로 유지한다.
자동 설치/재부팅 및 host OS 교체는 이 구현의 기능이 아니다.
