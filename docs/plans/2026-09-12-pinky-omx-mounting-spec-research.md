# 핑키프로와 OMX 탑재 사양 조사

> 2026-09-13 편입 안내: 이 문서는 작성 당시의 조사·평가 근거다. 현재 제품 경계와 구현 순서는 [ADR D-37~D-44](../reference/ROSY%20ADR%20Log.md), [흡수 실행 계획](2026-09-12-rosy-control-absorption-plan.md), [최신 실행 결과](2026-09-12-control-absorption-results.md)를 우선한다. 조사 당시의 미실행·별도 Control 표기는 현재 배포 상태를 뜻하지 않는다.

조사일: 2026-09-12. 대상: 바닥의 소형 박스를 수거하여 로봇에 적재하고 하역·적층하는 이동형 로봇암.
상태: 공식 사양·도면 조사 완료. 실물 하중·장착·전도 시험 미수행. 직접 탑재 승인 아님.

## 결론
핑키프로 외형은 110 × 120 × 142 mm이고, 신형 OMX-F 기본판은 120 × 150 mm이다. 기본판 돌출과 상부 LiDAR 때문에 장착·센서 시야·박스 적재 공간을 함께 검토해야 한다. 이 치수 비교만으로 직접 탑재가 불가능하거나 기계적으로 부적합하다고 확정할 수는 없다. 맞춤 고정부와 하중 전달 구조도 후보이며, 핑키프로 실제 무게·허용 적재하중·상판 허용 모멘트·보조전원 출력이 확인되지 않아 직접 탑재는 HOLD다.

> 재조사 보완: 사용자는 OMX 모델이 아직 결정 전이라고 확인했다. 장착판 크기만으로 탑재 불가를 단정한 이전 해석을 수정했다. 전체 개념과 대안·검증 계획은 [통합 재조사](2026-09-12-mobile-manipulation-research.md)를 따른다.

## 모델 정정
이전 대화는 OMX를 OpenMANIPULATOR-X RM-X52-TNM으로 가정했다. 현재 ROBOTIS는 OMX-F/OMX-L과 구형 OpenMANIPULATOR-X를 별도 제품으로 구분한다. 사용자가 말한 정확한 OMX 모델은 아직 확정하지 않았다. 구형의 700g / 500g / 380mm를 신형에 적용하면 안 된다.

## 핑키프로 공식 사양
제조사 저장소 README가 안내하는 [공식 소개](https://github.com/pinklab-art/pinky_study/wiki)의 이미지 원본을 내려받아 직접 판독했다.
- [제품 사진](https://github.com/user-attachments/assets/041ab0f0-545a-4c37-a9d7-4ae0c5d9f57c)
- [상세 제원 이미지](https://github.com/user-attachments/assets/db587eb8-d453-4fcc-a5b0-3ce6f29b7113)

| 항목 | 공식 표기 |
|---|---|
| 외형 W × D × H | 110 × 120 × 142 mm |
| SBC | Raspberry Pi 5, 8GB |
| 카메라 | 5MP |
| 구동 모터 | DYNAMIXEL XL330-M288-T |
| LiDAR | SLAMTEC RPLIDAR C1 |
| IMU | BNO055, 9축 |
| 초음파 / IR | US-016 / TCRT5000 |
| 화면 / LED | ST7789 2.4inch / WS2812B |
| 배터리 | 리튬이온, 전압·용량·외부 출력 미기재 |
| 본체 무게 / 허용 적재하중 | 확인한 공식 자료에서 미확인 |
| 상판 장착홀 / 허용 모멘트 | 미확인 |

사진에서 상부 LiDAR, 전면 LCD·카메라·초음파 배치를 확인했다. 외형 110×120은 자유롭게 쓸 수 있는 적재 면적이 아니다.
[공식 ROS 저장소](https://github.com/pinklab-art/pinky_pro)는 Ubuntu 24.04 / ROS 2 Jazzy 환경을 안내한다.

## OMX 모델별 공식 사양

| 항목 | 신형 OMX-F | 구형 OpenMANIPULATOR-X |
|---|---|---|
| 자체 무게 | 560g | 700g |
| 팔 자유도 | 5 + 그리퍼 | 4 + 그리퍼 |
| 최대 도달 | 400mm | 380mm |
| 가반하중 | full reach 100g, normal reach 250g | 500g |
| 전원 | 12VDC | 12V |
| 호스트 연결 | USB-C, OpenRB-150 | U2D2 또는 OpenCR |
| 내부 통신 | TTL, 1Mbps | TTL multidrop |
| 그리퍼 폭 | 텍스트에서 미확인 | 20–75mm |

출처: [OMX 하드웨어](https://ai.robotis.com/omx/hardware_omx.html), [구형 사양](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/specification/), [구형 설치·전원](https://emanual.robotis.com/docs/en/platform/openmanipulator_x/quick_start_guide/).
OMX-L은 360g / 5V의 leader 조작 장치로, 적재 작업용 follower와 다르다.
normal reach의 구체적인 거리·자세는 확인한 표에 정의되지 않았다. 400mm에서 250g을 들 수 있다는 의미가 아니다.
구형 권장 12V 5A 공급기는 상시 소비전류가 아니며, 이를 신형 OMX-F 요구치로 전용하지 않는다.

## OMX-F 도면 직접 판독
[공식 도면 이미지](https://docs.robotis.com/assets/images/omx_follower_layout-045a39b46c53c8684fbad95c81c1180b.png), 도면일 2025/08/20, 단위 mm, FOR REFERENCE ONLY.
- 기본판 외곽: 120 × 150 mm, 두께 13 mm.
- 도면에 표시된 자세의 평면 전장: 375.5 mm, 전체 높이 277 mm. 자세에 따라 변하는 외형이며 최대 작업공간 치수가 아니다.
- 장착홀: 4-Ø5.5 관통 / 카운터보어 Ø10 깊이5, 6-Ø6.5 관통 / 카운터보어 Ø13 깊이6.
- 두 홀 열 사이 125mm. 6개 홀 패턴은 열당 50+50mm, 중간 4개 홀의 위치는 중앙 기준 ±25mm로 표시.
- 홀 위치는 가공 전에 공식 CAD 및 실물과 대조해야 한다.
[공식 PDF](https://www.robotis.com/service/download.php?no=2223), [STEP](https://www.robotis.com/service/download.php?no=2224)는 다운로드 안내를 확인했으며 CAD 형상 검증은 하지 않았다.

## 탑재 시 판단
1. 크기: 120×150 기본판은 110×120 베이스 전체 외형보다 크다. 그 위에 박스 적재 공간과 LiDAR 시야까지 필요하다. 기본판 유지 직접 탑재를 기본안으로 확정하지 않는다.
2. 하중: OMX-F 560g + full reach 작업물 100g = 660g. 이는 두 수치 단순 합이며, 추가 부품·적재함·배선·전원·다른 박스가 빠져 있다. 560g 무게의 세부 포함 범위도 구매 구성과 대조해야 한다.
3. 전도: 작업물 100g을 수평 0.4m에 둔다고 가정하면 작업물만의 모멘트는 약 0.392N·m이다. 실제 회전축 기준거리와 암 자체 무게중심·지지다각형이 필요하므로 안전 판정 계산이 아니다.
4. 도달: 400mm 최대 도달만으로 바닥 집기를 보장할 수 없다. 장착 높이, 관절 제한, 손가락과 바닥 간섭, 접근·후퇴 자세를 확인해야 한다.
5. 전원: 핑키의 리튬이온 배터리 표기만으로 OMX용 12V 전원 공급 가능을 판단할 수 없다.
6. ROS: 공통 ROS2 환경은 소프트웨어 통합 후보 근거다. 기계·전원 탑재 허용이나 Pi에서 동시 실행 성능의 증거는 아니다.

## 로봇 모델과 실물 사양의 구분
[제조사 URDF](https://raw.githubusercontent.com/pinklab-art/pinky_pro/main/pinky_description/urdf/pinky.urdf.xacro)에 base_link 0.8kg, 바퀴 링크 각 0.2kg 등의 모델 질량이 존재한다. 이를 핑키프로 실제 제품 무게 또는 허용 적재하중으로 인용하지 않는다. 바퀴 joint y=±0.04055m도 모델 좌표이며 실물 지지 폭 검증을 대체하지 않는다.

## 다음에 필요한 실물·제조사 정보
정확한 OMX 모델, 핑키 배터리 포함 무게, 허용 적재하중, 상판 구조와 체결홀, 바퀴 접촉점과 무게중심, 12V 공급 가능 용량, 암을 낮게 장착했을 때 바닥·적재함 도달 범위.
직접 탑재가 어려우면 고정 OMX 작업대 + 핑키 운반 또는 더 넓은 이동 베이스가 대안이다. 소프트웨어 작업 조율은 두 배치에 재사용할 수 있다.
