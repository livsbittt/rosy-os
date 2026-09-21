# signal/observer — 신호등 관측 서비스 (읽기 전용)

설계: `docs/plans/2026-09-22-signal-observer-vision-design.md`
경계: **명령 경로가 없다.** 이 서버는 증거(`GET /observed`)만 내어준다. 제어는
ESP32 컨트롤러와 Fleet 콘솔의 몫이다.

## 실행

```bash
python signal/observer/observer.py --config signal/observer/config.example.json \
    --host 127.0.0.1 --port 8095
curl http://127.0.0.1:8095/observed
```

설정 JSON: 카메라 인덱스, 렌즈 ROI(left/mid/right/beacon — 픽셀 좌표는 설치 후
캘리브레이션), 꺼짐 판정 문턱(`lit_value_min`, `lit_sat_min`). 예시는
`config.example.json`.

## 응답

```json
{ "ts": 1770000000.0,
  "lamps":  { "left": {"lit": true, "group": "red", "confidence": 0.91}, ... },
  "stable": { "left": {"lit": true, "group": "red", "pending": false}, ... } }
```

- `lamps` — 이 프레임의 **날 판정**. 같은 프레임이면 같은 답(결정론).
- `stable` — `stable_after`(기본 2)프레임 연속 일치할 때만 바뀌는 **안정 상태**.
  화면·기록·Fleet 교차 검증은 이쪽을 쓴다. `pending: true` 면 아직 확정 전.

`group`은 색상군(red/orange/green/blue)이지 의미가 아니다 — stop/go 해석은
운영자의 사이클 지도가 한다(v2 제안 §2.1).

## 캘리브레이션 (프리뷰)

카메라가 보는 화면에 ROI 박스와 판정을 그려서 돌려준다 — 픽셀 좌표를 눈으로
맞추지 않게 하는 조격이다:

```bash
curl http://127.0.0.1:8095/observed      # 프레임 확보 (1회)
curl -o preview.jpg http://127.0.0.1:8095/preview.jpeg
```

박스가 렌즈와 어긋나면 `observer.json` 의 ROI 좌표를 고치고 관측을 다시 호출한다.

## 라즈베리파이 상시 기동

`rosy-signal-observer.service` 유닛을 제공한다. 설정 `source` 를
`{"type": "picamera2"}` 로 두고(unit 의 전제 참고) systemd 로 등록하면 상시
관측이 된다. Windows 벤치와 같은 분류 코드 — 소스만 바뀐다.

## 검증

```bash
python -m pytest signal/observer/test -q
```

합성 프레임 시험(23건) — 실촬 프레임 회귀 세트는 벤치에서 수집해 합류시킨다
(합성 ≠ DEVICE).
