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
  "lamps": { "left": {"lit": true, "group": "red", "confidence": 0.91}, ... } }
```

`group`은 색상군(red/orange/green/blue)이지 의미가 아니다 — stop/go 해석은
운영자의 사이클 지도가 한다(v2 제안 §2.1).

## 검증

```bash
python -m pytest signal/observer/test -q
```

합성 프레임 시험(14건) — 실촬 프레임 회귀 세트는 벤치에서 수집해 합류시킨다
(합성 ≠ DEVICE).
