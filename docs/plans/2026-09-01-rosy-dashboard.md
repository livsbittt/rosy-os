# Rosy OS Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** FastAPI에 내장되는 경량 Rosy OS 운영 대시보드와 Raspberry Pi OS 읽기 전용 상태 API를 구현한다.

**Architecture:** `HostRuntimeProbe`가 지정된 host root에서 Linux 상태를 안전하게 수집하고 FastAPI 시스템 라우터가 이를 제공한다. 프론트엔드는 패키지에 포함된 정적 HTML/CSS/JavaScript이며 기존 REST/WebSocket·인증·안전 API만 소비한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, HTML5, CSS, vanilla ES modules, Docker Compose.

---

### Task 1: Host runtime probe

**Files:**
- Create: `src/rosy_core/test/test_host_runtime.py`
- Create: `src/rosy_core/rosy_core/system/__init__.py`
- Create: `src/rosy_core/rosy_core/system/runtime.py`

**Step 1: Write failing tests**

임시 `/host` 트리에 `proc/uptime`, `proc/loadavg`, `proc/meminfo`, `sys/class/thermal/thermal_zone0/temp`, `etc/os-release`, `etc/hostname`을 만들고 정규화된 결과, 누락 파일의 `null`, 비밀값 미노출을 검증한다.

**Step 2: Verify RED**

Run: `python -m pytest test/test_host_runtime.py -q`
Expected: FAIL because `rosy_core.system.runtime` does not exist.

**Step 3: Implement minimal probe**

표준 라이브러리만 사용해 OS, hostname, architecture, uptime, load, memory, disk, temperature, network, collection timestamp를 반환한다. 모든 파일 읽기는 제한된 경로와 예외 처리 안에서 수행한다.

**Step 4: Verify GREEN**

Run: `python -m pytest test/test_host_runtime.py -q`
Expected: PASS.

### Task 2: FastAPI system runtime contract

**Files:**
- Modify: `src/rosy_core/rosy_core/services.py`
- Modify: `src/rosy_core/rosy_core/api/v1/routes.py`
- Modify: `src/rosy_core/test/test_api.py`

**Step 1: Write failing API tests**

viewer 인증 없이는 401, viewer 인증으로 `/api/v1/system/runtime`은 안전한 상태 문서를 반환하며 토큰과 전체 환경변수를 노출하지 않는지 검증한다.

**Step 2: Verify RED**

Run: `python -m pytest test/test_api.py -q`
Expected: FAIL with 404.

**Step 3: Add injected runtime probe and route**

`CoreServices`에 probe를 주입하고 `system_router`에 읽기 전용 endpoint를 추가한다.

**Step 4: Verify GREEN**

Run: `python -m pytest test/test_api.py -q`
Expected: PASS.

### Task 3: Embedded dashboard shell and package assets

**Files:**
- Create: `src/rosy_core/test/test_dashboard.py`
- Create: `src/rosy_core/rosy_core/web/index.html`
- Create: `src/rosy_core/rosy_core/web/styles.css`
- Create: `src/rosy_core/rosy_core/web/app.js`
- Modify: `src/rosy_core/rosy_core/api/app.py`
- Modify: `src/rosy_core/setup.py`
- Modify: `src/rosy_core/package.xml`

**Step 1: Write failing route and asset tests**

`/dashboard`, `/dashboard/assets/styles.css`, `/dashboard/assets/app.js`의 상태·콘텐츠 타입·핵심 접근성 표식을 검증한다.

**Step 2: Verify RED**

Run: `python -m pytest test/test_dashboard.py -q`
Expected: FAIL with 404.

**Step 3: Implement dashboard**

FastAPI `StaticFiles`와 `FileResponse`로 자산을 제공하고, 화면에는 연결·안전·로봇·OS·기능·이벤트 패널, 토큰 입력, 모드 변경, 비상정지와 명확한 오류 상태를 구현한다.

**Step 4: Verify GREEN**

Run: `python -m pytest test/test_dashboard.py -q`
Expected: PASS.

### Task 4: Raspberry Pi host telemetry mounts

**Files:**
- Modify: `deploy/robot/compose.yaml`
- Modify: `deploy/robot/.env.example`
- Modify: `deploy/robot/Dockerfile`
- Modify: `test/test_robot_runtime.py`

**Step 1: Write failing runtime contract tests**

core 서비스가 host 상태 파일을 read-only로 마운트하고 `ROSY_HOST_ROOT=/host`를 받으며 웹 자산이 이미지에 포함되는지 검증한다.

**Step 2: Verify RED, implement, verify GREEN**

Run: `python -m pytest test/test_robot_runtime.py -q`
Expected before: FAIL. Expected after: PASS.

### Task 5: Documentation and end-to-end verification

**Files:**
- Modify: `README.md`
- Modify: `docs/deployment/raspberry-pi-runtime.md`

**Steps:**

1. 대시보드 URL, 인증, host mount, 읽기 전용 안전 경계와 장애 표시를 문서화한다.
2. 전체 pytest, compileall, Compose config, Docker core build를 실행한다.
3. 실제 FastAPI를 기동해 API와 UI를 브라우저 크기별로 확인하고 콘솔 오류·접근성·반응형 레이아웃을 검증한다.
4. `git diff --check`와 최종 코드 리뷰 후 커밋한다.
