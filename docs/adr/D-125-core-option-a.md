## D-125 Core 패키지를 논리적 도메인 라이브러리로 분할 (Option A)

**Status:** Accepted (2026-09-19). 모놀리식 core 패키지를 논리적인 단위의 하위 ROS 패키지로 분리하되 단일 노드(Single Process) 아키텍처는 유지한다.

**Context:** 기존 `rosy_core` (현재 `core/core`) 패키지 내부에 api, web, safety, docking, power, navigation 등 모든 도메인 로직이 집중된 모놀리식 구조였다. 프로젝트 규모가 커짐에 따라 코드 결합도를 낮추고 모듈의 독립성을 보장할 필요가 제기되었다. 다중 프로세스(Multi-node)로 분할하는 방안(Option B)도 고려되었으나, 기존의 의존성 주입(`CoreServices`)과 인메모리 `EventBus`를 ROS Topic으로 전면 교체하는 비용이 너무 크고, 아직 물리적 노드 분산의 이점이 뚜렷하지 않다고 판단되었다.

**Decision:** 

- D-1(단일 프로세스 원칙)을 준수하여, 런타임에는 여전히 `core_node`라는 하나의 ROS 노드로 실행된다.
- 소스 코드 레벨에서는 `core` 패키지를 다음과 같은 여러 개의 독립적인 ament_python 패키지(도메인 라이브러리)로 쪼갠다.
  - `core_common`: `identity`, `config`, `protocol`, `capability` 등 핵심 데이터 클래스
  - `core_events`: 인메모리 이벤트 버스
  - `core_features`: `safety`, `power`, `docking`, `navigation` 등 도메인 로직
  - `core_api_web`: `api`, `web` 프론트 및 통신부
  - `core_node`: 위의 모든 라이브러리를 의존성으로 가져와 `main.py`와 `node.py`에서 DI 컨테이너를 조립하고 실행하는 진입점
- 기존의 `module-split-criteria.md`에 명시된 "크기는 분리 기준이 아니다" 등의 엄격한 사내 규칙은, 이번 아키텍처 단위의 도메인 라이브러리 분할(Macro-level split)에는 예외적으로 적용하지 않거나 갱신한다. (마이크로 레벨의 단일 파일 분할 규칙은 유지)

**Alternatives:** 
- Option B (완전한 물리적 마이크로서비스 분할): 각 기능을 별도의 ROS 2 노드로 쪼개는 방식. 구현 및 통신 오버헤드, 디버깅 복잡도 증가로 인해 현 시점에서는 보류.
- 기존 모놀리식 유지: 결합도가 지속적으로 상승하여 유지보수성이 저하되므로 반려.

**Consequences:** 
- `core/` 디렉토리 아래에 여러 개의 ROS 패키지(라이브러리)가 생성된다.
- `colcon build` 시 패키지 간의 의존성(dependency) 트리가 명확해진다.
- 런타임 아키텍처는 변하지 않으므로 기존 테스트 코드의 파괴를 최소화할 수 있으나, 패키지 분리에 따른 `import` 경로 대거 수정이 필요하다.

**Validation / Transition:** 
- 1단계 작업으로 파이썬 모듈들을 논리적 패키지 폴더로 분리하고 `package.xml`과 `setup.py`를 작성한다.
- `colcon build` 정상 통과 및 기존 `pytest` 유닛 테스트 성공 여부 확인.

**References:** D-1, module-split-criteria.md

---
