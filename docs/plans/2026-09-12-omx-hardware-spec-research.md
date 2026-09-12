# OMX 하드웨어 사양 조사 — Pinky Pro 탑재 검토

> 2026-09-13 편입 안내: 이 문서는 작성 당시의 조사·평가 근거다. 현재 제품 경계와 구현 순서는 [ADR D-37~D-44](../reference/ROSY%20ADR%20Log.md), [흡수 실행 계획](2026-09-12-rosy-control-absorption-plan.md), [최신 실행 결과](2026-09-12-control-absorption-results.md)를 우선한다. 조사 당시의 미실행·별도 Control 표기는 현재 배포 상태를 뜻하지 않는다.

조사일: 2026-09-12. 제조사 공식 문서만 사용했다. 이 문서는 조사 기록이며 API 계약이나 탑재 승인 문서가 아니다.

> 후속 조사 안내: 이 문서는 초기 모델 식별 기록이다. 이후 사용자는 OMX 모델이 아직 결정 전이라고 확인했다. 핑키·OMX-F 치수 이미지 판독은 [사양 조사](2026-09-12-pinky-omx-mounting-spec-research.md), 현재 판단과 검증 순서는 [통합 재조사](2026-09-12-mobile-manipulation-research.md)를 우선한다.

## 모델 식별이 먼저 필요함

ROBOTIS는 **OMX-F / OMX-L / OMX-AI**와 **OpenMANIPULATOR-X (RM-X52-TNM)**를 별도 제품으로 안내한다. 대화에서 OMX를 곧바로 RM-X52-TNM으로 해석한 것은 확정할 수 없다. 사용자가 말한 OMX의 정확한 모델에 따라 무게·자유도·가반하중이 달라진다. [OMX 소개](https://ai.robotis.com/omx/introduction_omx.html), [RM-X52-TNM 공식 상품](https://en.robotis.com/shop_en/item.php?it_id=905-0024-000)

## 확인한 사양

| 항목 | OMX-F (현행 OMX follower) | OpenMANIPULATOR-X RM-X52-TNM |
|---|---|---|
| 팔 자체 무게 | 560 g | 700 g (관성 자료 합계 711.37 g) |
| 자유도 | 팔 5 + 그리퍼 1 | 팔 4 + 그리퍼 1 |
| 최대 도달 거리 | 400 mm | 380 mm |
| 가반하중 | 최대 신장 100 g / normal reach 250 g | 500 g |
| 입력 전압 | 12 VDC | 12 V |
| 그리퍼 폭 | 이번에 확인한 텍스트 사양에는 없음 | 20–75 mm |
| 호스트 연결 | USB-C | U2D2 또는 OpenCR 경로 |
| 내부 통신 | TTL, 1 Mbps | TTL multidrop bus |
| 구동기 | XL430-W250-T × 3, XL330-M288-T × 3 | XM430-W350-T |

출처: [OMX 하드웨어](https://docs.robotis.com/docs/systems/omx/specifications/hardware/), [OpenMANIPULATOR-X 사양](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/specification/), [구형 연결 및 전원 안내](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/quick_start_guide/).

OMX의 normal reach가 어느 거리·자세를 뜻하는지는 사양 표에 정의되지 않았다. 250 g을 400 mm 전체 작업 공간의 허용 무게로 사용하면 안 된다. OMX-L은 조작용 leader로 360 g / 335 mm / 5 V이며 실제 박스를 드는 follower와 구분한다. [공식 하드웨어](https://ai.robotis.com/omx/hardware_omx.html)

## 전원·소프트웨어

구형 RM-X52-TNM은 제조사가 12 V 5 A SMPS를 권장한다. 이는 공급기 사양이며 상시 소비 전류가 아니다. 이 권장값을 신규 OMX-F의 소비전류로 옮겨 적으면 안 된다. 신규 OMX 세트에는 DC converter와 OpenRB-150이 포함되지만 Pinky 전원 분기 허용 전류는 별도로 확인해야 한다. [구형 Quick Start](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/quick_start_guide/), [OMX 구성품](https://ai.robotis.com/omx/hardware_omx.html)

OMX 소프트웨어 문서는 ROS 2 Jazzy, ros2_control, 100 Hz 관절 제어 구조를 설명한다. 구형은 Jazzy/Humble 안내가 각각 있다. ROS 지원은 Pinky와의 실제 전원·기구 결합 또는 ARM64 온보드 성능 검증을 대신하지 않는다. [OMX 소프트웨어](https://ai.robotis.com/omx/software_omx.html), [구형 설치 안내](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/quick_start_guide/)

## 장착 도면과 남은 확인

- OMX-F 공식 [PDF](https://www.robotis.com/service/download.php?no=2223), [STEP](https://www.robotis.com/service/download.php?no=2224), [레이아웃 이미지](https://docs.robotis.com/assets/images/omx_follower_layout-045a39b46c53c8684fbad95c81c1180b.png)가 제공된다.
- 구형의 [공식 치수 이미지](https://emanual.robotis.com/assets/images/platform/openmanipulator_x/OpenManipulator_Chain_spec_side.png)와 공식 상품 페이지의 CAD 링크가 있다.
- 이번 웹 텍스트 조회에서 PDF/STEP은 다운로드 안내 페이지만 반환했다. 이미지의 치수를 시각 판독하지 않았으므로 **장착면 외곽·볼트 홀 간격·체결 규격·바닥 도달 높이를 확정하지 않았다.** 최대 reach를 수직 하방 도달 거리로 취급하면 안 된다.
- Pinky 상판/지지 다각형/무게중심과 암 전체 자세별 질량 중심을 결합해야 전도 안정성을 계산할 수 있다.
- 총 적재량에는 팔, 브래킷, 카메라, 전원 부품, 적재 중인 박스를 모두 포함해야 한다. 팔의 가반하중과 베이스의 적재 허용량은 서로 다른 제한이다.

## 판단

정확한 OMX 모델 식별 없이 700 g·500 g 사양을 사용자 장치에 적용하면 안 된다. 신규 OMX-F라면 박스 시험은 full reach 100 g 제한을 고려해야 한다. 현 상태는 소프트웨어 연결 후보 확인이며 Pinky 탑재 가능 판정은 기구·전원 도면 및 실제 장치 확인 전까지 보류한다.
