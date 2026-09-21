## D-85 도크 펌웨어 ARTIFACT는 ESP32 툴체인 증거다

**Status:** Accepted (2026-09-17).

**Context:** `dock/firmware/rosy_dock/rosy_dock.ino`는 참조 구현이다. HOST
pytest(`test_dock_contract.py`)는 README와 파서 계약만 본다. ESP32 툴체인이
없는 Windows에서 펌웨어 빌드 없이 ARTIFACT GO를 쓰려는 시도가 있다.

**Decision:** 도크 ARTIFACT GO는 **Arduino/ESP32 빌드·플래시 readback**이 있을
때만이다. HOST 계약 시험은 SOURCE/LOCAL이다. 툴체인 없는 호스트는 HOLD다.
물리 벤치 통전은 DEVICE다.

**Alternatives:** `.ino` 존재만으로 ARTIFACT를 닫는 안은 계층을 속인다.

**Consequences:** `dock` SOURCE/LOCAL GO는 펌웨어 발행이 아니다.

**Validation / Transition:** `dock/progress.md` ARTIFACT blocker. HOST
`test/test_dock_contract.py`.

**References:** D-27, D-28, D-36, D-79.

---
